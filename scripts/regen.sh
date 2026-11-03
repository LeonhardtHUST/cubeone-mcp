#!/usr/bin/env bash
# =============================================================================
# platform32-mcp / scripts/regen.sh
#
# 「备份 .ioc → CubeMX 生成 → 生成核验」三步封装 + 失败回滚。
#
# 为什么需要这层封装
# ------------------
# CubeMX 对 .ioc 的错误是**静默非致命**的（调研报告 C2、模板 D5、HAL-PITFALLS H-6）：
# 信号名写错 / 参数没进 IPParameters 白名单，`project generate` 依然返回"成功"，
# 外设被静默丢弃。所以"生成完了"这句话只有在核验器过了之后才成立。
# 本脚本保证：任何一步失败，都回到生成前的 .ioc，绝不把未核验的配置留在工作区。
#
# 用法
# ----
#   scripts/regen.sh <工程目录> [选项]
#
#   -e, --expect <list>        期望外设清单（如 GPIO,TIM4,USART2）
#                              默认：从 .ioc 的 Mcu.IP* 推导（滤掉 NVIC/RCC/SYS）+ 补 GPIO
#   -l, --log <path>           CubeMX 生成日志路径（默认 <out>/cubemx-generate.log）
#   -m, --mx <script.mx>       CubeMX 脚本（默认 <工程>/scripts/cubemx-generate.mx）
#   -o, --out <dir>            证据输出目录（默认 ${TMPDIR:-/tmp}/platform32-regen）
#       --java <path>          java 可执行（默认取 $ST_CUBEMX_JRE 或 C:/ST/STM32CubeMX/jre/bin/java.exe）
#       --cube <path>          CubeMX 可执行（默认取 $ST_CUBEMX_EXE 或 C:/ST/STM32CubeMX/STM32CubeMX.exe）
#       --timeout <sec>        生成超时，最小 240（默认 300；单次生成实测约 60s）
#       --allow-signal <sig>   传给核验器的 Cannot map 白名单（默认已含 VP_RIF_VS_RIF1，D8 噪音）
#       --no-default-allow     不预置 D8 白名单
#       --allow-dirty-ioc      允许 .ioc 处于未提交改动时继续（默认拒绝，避免回滚丢用户改动）
#       --keep-ask-for-migrate 生成成功后**不**把 ProjectManager.AskForMigrate 复位为 false
#       --skip-generate        跳过生成，只做备份 + 核验（重跑核验用）
#       --dry-run              只打印将执行的命令，不落盘
#   -h, --help
#
# 生成前强制前置检查（provenance：实测 `stm32-digital-clock` 的 .ioc 就是 true）
# ---------------------------------------------------------------------------
# `ProjectManager.AskForMigrate=true` 会让 `-q` 非交互生成**卡在迁移对话框**直到
# 超时（300s 白等，且从超时现象看不出根因）。所以命中即 **退出 2，不进生成**。
# 生成成功后本脚本会把该行复位成 `false`（用 scripts/ioc_field.py 精确改单行），
# 否则下一次生成必被这条前置拦死。想观察 CubeMX 原始行为用 `--keep-ask-for-migrate`。
#
# 退出码
# ------
#   0 = 生成 + 核验全部通过（允许 warning，如 D9 的 syscalls/sysmem 叠加路径）
#   1 = 生成失败或核验 fail（已回滚）
#   2 = 参数/IO/环境错误，或前置检查拒绝（.ioc 脏 / AskForMigrate=true / 缺 .mx）
#
# 约定
# ----
# * **不做配置类文本注入**：改引脚/外设/参数一律走 CubeMX CLI（set 命令）或 MCP。
#   唯一的写盘例外是 `AskForMigrate` 这个**弹窗开关**（非配置项）的复位，见上。
# * **CubeMX 的 cwd 必须是工程根**：`cubemx-generate.mx` 里 `config load` 用的是相对
#   `.ioc` 路径，而 CubeMX 默认 cwd 是安装目录。本脚本在子 shell 里 cd 进工程根，
#   并在执行前断言 cwd 正确，不满足直接退出 2。
# * 回滚优先用 git（调研报告 C5：回滚粒度是 git），非 git 工程退化为 .ioc.bak。
# * 工程目录由参数传入，脚本内不写死任何工程路径。
# =============================================================================
set -uo pipefail

# Git Bash 下 PATH 常缺 coreutils（timeout/cp/…），统一补齐。
export PATH="/c/Users/Leon/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Leon/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${PYTHON:-python}"

DEFAULT_JAVA="${ST_CUBEMX_JRE:-C:/ST/STM32CubeMX/jre/bin/java.exe}"
DEFAULT_CUBE="${ST_CUBEMX_EXE:-C:/ST/STM32CubeMX/STM32CubeMX.exe}"
MIN_TIMEOUT=240
#: 本机锁定的 CubeMX 基线版本（决策 D1）；`.ioc` 版本戳不一致只告警，不阻塞。
EXPECTED_CUBEMX_VERSION="${EXPECTED_CUBEMX_VERSION:-6.18.1}"

PROJECT_DIR=""
EXPECT=""
GEN_LOG=""
MX_SCRIPT=""
OUT_DIR="${TMPDIR:-/tmp}/platform32-regen"
JAVA_BIN="${DEFAULT_JAVA}"
CUBE_BIN="${DEFAULT_CUBE}"
TIMEOUT_SEC=300
SKIP_GENERATE=0
DRY_RUN=0
ALLOW_DIRTY_IOC=0
DEFAULT_ALLOW=1
RESET_ASK_FOR_MIGRATE=1
ALLOW_SIGNALS=()

log_info() { printf '[regen] %s\n' "$*" >&2; }
log_warn() { printf '[regen][warn] %s\n' "$*" >&2; }
log_err()  { printf '[regen][error] %s\n' "$*" >&2; }

usage() {
  sed -n '2,50p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

die() {
  local code="$1"; shift
  log_err "$*"
  exit "$code"
}

# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
while [ "$#" -gt 0 ]; do
  case "$1" in
    -e|--expect)        EXPECT="${2:-}"; shift 2 ;;
    -l|--log)           GEN_LOG="${2:-}"; shift 2 ;;
    -m|--mx)            MX_SCRIPT="${2:-}"; shift 2 ;;
    -o|--out)           OUT_DIR="${2:-}"; shift 2 ;;
    --java)             JAVA_BIN="${2:-}"; shift 2 ;;
    --cube)             CUBE_BIN="${2:-}"; shift 2 ;;
    --timeout)          TIMEOUT_SEC="${2:-}"; shift 2 ;;
    --allow-signal)     ALLOW_SIGNALS+=("${2:-}"); shift 2 ;;
    --no-default-allow) DEFAULT_ALLOW=0; shift ;;
    --allow-dirty-ioc)  ALLOW_DIRTY_IOC=1; shift ;;
    --keep-ask-for-migrate) RESET_ASK_FOR_MIGRATE=0; shift ;;
    --skip-generate)    SKIP_GENERATE=1; shift ;;
    --dry-run)          DRY_RUN=1; shift ;;
    -h|--help)          usage; exit 0 ;;
    -*)                 die 2 "未知选项：$1（--help 看用法）" ;;
    *)
      if [ -z "$PROJECT_DIR" ]; then PROJECT_DIR="$1"; shift
      else die 2 "多余的参数：$1（工程目录只接受一个）"; fi ;;
  esac
done

[ -n "$PROJECT_DIR" ] || die 2 "缺少工程目录参数（--help 看用法）"
[ -d "$PROJECT_DIR" ] || die 2 "工程目录不存在：$PROJECT_DIR"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

command -v "$PYTHON" >/dev/null 2>&1 || die 2 "找不到 python 解释器：$PYTHON（可用 PYTHON=... 覆盖）"

# 超时阈值不得低于 240s（单次生成约 60s，JVM 启动 + CMSIS 拷贝占大头）。
case "$TIMEOUT_SEC" in
  ''|*[!0-9]*) die 2 "--timeout 必须是整数秒：$TIMEOUT_SEC" ;;
esac
if [ "$TIMEOUT_SEC" -lt "$MIN_TIMEOUT" ]; then
  log_warn "--timeout ${TIMEOUT_SEC}s 过小，已提升到 ${MIN_TIMEOUT}s（CubeMX 单次生成约 60s，勿低于此值）"
  TIMEOUT_SEC="$MIN_TIMEOUT"
fi

if [ "$DEFAULT_ALLOW" -eq 1 ]; then
  # 注意 set -u 下空数组的展开要写法保护（老 bash 会报 unbound variable）。
  ALLOW_SIGNALS=("VP_RIF_VS_RIF1" ${ALLOW_SIGNALS[@]+"${ALLOW_SIGNALS[@]}"})
fi

# 去重（用户可能把默认的 D8 噪音又显式传一遍），保证证据里的命令干净。
DEDUPED_SIGNALS=()
for _sig in ${ALLOW_SIGNALS[@]+"${ALLOW_SIGNALS[@]}"}; do
  [ -n "$_sig" ] || continue
  _dup=0
  for _kept in ${DEDUPED_SIGNALS[@]+"${DEDUPED_SIGNALS[@]}"}; do
    if [ "$_kept" = "$_sig" ]; then _dup=1; break; fi
  done
  [ "$_dup" -eq 0 ] && DEDUPED_SIGNALS+=("$_sig")
done
ALLOW_SIGNALS=(${DEDUPED_SIGNALS[@]+"${DEDUPED_SIGNALS[@]}"})

# ---------------------------------------------------------------------------
# 前置检查：.ioc / .mxproject / main.c / .mx 脚本 / git 状态
# ---------------------------------------------------------------------------
IOC_FILES=()
while IFS= read -r line; do
  [ -n "$line" ] && IOC_FILES+=("$line")
done < <(find "$PROJECT_DIR" -maxdepth 1 -name '*.ioc' -type f | sort)
[ "${#IOC_FILES[@]}" -gt 0 ] || die 2 "工程目录下没有 .ioc：$PROJECT_DIR"
#: 主 .ioc（多 .ioc 的工程取字典序第一个；工程范式里只会有一个）
IOC_FILE="${IOC_FILES[0]}"

MAIN_C="${PROJECT_DIR}/Core/Src/main.c"
MXPROJECT="${PROJECT_DIR}/.mxproject"
[ -f "$MAIN_C" ] || die 2 "缺少生成物 Core/Src/main.c：$MAIN_C（先生成一次再核验）"
[ -f "$MXPROJECT" ] || die 2 "缺少 .mxproject：$MXPROJECT（先生成一次再核验）"

if [ -z "$MX_SCRIPT" ]; then
  if [ -f "${PROJECT_DIR}/scripts/cubemx-generate.mx" ]; then
    MX_SCRIPT="${PROJECT_DIR}/scripts/cubemx-generate.mx"
  else
    MX_SCRIPT="$(find "${PROJECT_DIR}/scripts" -maxdepth 1 -name '*.mx' -type f 2>/dev/null | sort | head -n 1)"
  fi
fi
[ -n "$MX_SCRIPT" ] || die 2 "找不到 CubeMX 脚本（默认找 <工程>/scripts/cubemx-generate.mx）；用 --mx 指定"
[ -f "$MX_SCRIPT" ] || die 2 "CubeMX 脚本不存在：$MX_SCRIPT"

IN_GIT=0
if ( cd "$PROJECT_DIR" && git rev-parse --is-inside-work-tree ) >/dev/null 2>&1; then
  IN_GIT=1
  DIRTY_IOC="$( cd "$PROJECT_DIR" && git status --porcelain -- '*.ioc' 2>/dev/null )"
  if [ -n "$DIRTY_IOC" ] && [ "$ALLOW_DIRTY_IOC" -eq 0 ]; then
    log_err ".ioc 存在未提交改动，回滚（git checkout -- *.ioc）会丢掉这些改动，已中止："
    printf '%s\n' "$DIRTY_IOC" >&2
    log_err "若这些改动**就是本次要验证的改动**（刚用 CLI set 改完），加 --allow-dirty-ioc 重跑："
    log_err "  bash scripts/regen.sh \"$PROJECT_DIR\" --allow-dirty-ioc -o <证据目录>"
    log_err "若是与本任务无关的 WIP，先 git stash / 提交，再重跑。"
    die 2 "拒绝在 .ioc 脏的工作区生成（见上方两条处置）"
  fi
else
  log_warn "工程不在 git 仓库内，回滚将退化为 .ioc.bak（无法回滚 Core/ 生成物）"
fi

# ---- 生成前强制前置：AskForMigrate=true 会让 -q 非交互生成卡在迁移对话框 ----
# 依据：TOOLING-cubemx.md §3.3（每次生成都会写回 true）、模板 D7；
# 真实样本：stm32-digital-clock.ioc 就是 true（由 CubeMX 6.17.0 生成）。
if grep -qE '^ProjectManager\.AskForMigrate=true' "$IOC_FILE" 2>/dev/null; then
  log_err "前置检查未通过：$IOC_FILE 含 ProjectManager.AskForMigrate=true"
  log_err "  → CubeMX 的 -q 非交互模式会停在迁移对话框，一直阻塞到超时（会白等 ${TIMEOUT_SEC}s）；"
  log_err "    而且从'超时'这个现象看不出根因，是最难排查的一类失败。"
  log_err "  处置（任选其一，本脚本不做配置注入）："
  log_err "    1) 用 CubeMX GUI 打开该 .ioc 并保存一次（会把该行写回 false）；"
  log_err "    2) 精确改这一行：python scripts/ioc_field.py --ioc \"$IOC_FILE\" set ProjectManager.AskForMigrate false"
  die 2 "AskForMigrate=true，已在生成前拦下（未调用 CubeMX）"
fi

# ---- 版本戳：只告警（提交卫生问题，不是正确性门）----
IOC_VERSION="$(grep -m1 -E '^MxCube\.Version=' "$IOC_FILE" 2>/dev/null | sed -E 's/^MxCube\.Version=//' | tr -d '\r')"
if [ -n "$IOC_VERSION" ] && [ "$IOC_VERSION" != "$EXPECTED_CUBEMX_VERSION" ]; then
  log_warn ".ioc 版本戳 MxCube.Version=${IOC_VERSION} ≠ 锁定版本 ${EXPECTED_CUBEMX_VERSION}（P2）："
  log_warn "  重新生成会把整份 .ioc 重写成新版本格式（本机实测 619 增/106 删），建议拆成独立提交。"
fi

# 期望外设：默认从 .ioc 的 Mcu.IP* 推导，滤掉 NVIC/RCC/SYS，再补 GPIO。
if [ -z "$EXPECT" ]; then
  IP_LIST="$(grep -hE '^Mcu\.IP[0-9]+=' "${IOC_FILES[@]}" 2>/dev/null \
    | sed -E 's/^Mcu\.IP[0-9]+=//' | tr -d '\r' \
    | grep -vE '^(NVIC|RCC|SYS|DBGMCU)$' | sort -u | paste -sd, -)"
  EXPECT="GPIO${IP_LIST:+,${IP_LIST}}"
  log_info "未指定 --expect，按 .ioc 推导：${EXPECT}"
fi

mkdir -p "$OUT_DIR" || die 2 "无法创建输出目录：$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
[ -n "$GEN_LOG" ] || GEN_LOG="${OUT_DIR}/cubemx-generate.log"
VERIFY_JSON="${OUT_DIR}/verify.json"
VERIFY_MD="${OUT_DIR}/verify.md"
BACKUP_JSON="${OUT_DIR}/ioc-backup.json"

log_info "工程：${PROJECT_DIR}"
log_info "期望外设：${EXPECT}"
log_info "证据输出：${OUT_DIR}"
ALLOW_DISPLAY="（空：任何 Cannot map 都会 fail）"
[ "${#ALLOW_SIGNALS[@]}" -gt 0 ] && ALLOW_DISPLAY="${ALLOW_SIGNALS[*]}"
# 生效的白名单必须显式打印：verify 直调（无默认）与 regen.sh（预置 D8）默认值不同，
# 不打出来就会出现"同一份日志、两个入口、两种结论"。
log_info "生效 allowlist：${ALLOW_DISPLAY}（同时写进 verify.json 的 inputs.effective_allow_signals）"

# ---------------------------------------------------------------------------
# 回滚
# ---------------------------------------------------------------------------
rollback_project() {
  log_warn "开始回滚到生成前状态 ..."
  if [ "$IN_GIT" -eq 1 ]; then
    if ( cd "$PROJECT_DIR" && git checkout -- '*.ioc' ) 2>/dev/null; then
      log_info "已 git checkout -- '*.ioc'"
    else
      log_warn "git checkout .ioc 失败，改用 .ioc.bak"
      "$PYTHON" "${SCRIPT_DIR}/ioc_backup.py" --project "$PROJECT_DIR" --restore >&2 || true
    fi
    if ( cd "$PROJECT_DIR" && git ls-files --error-unmatch -- '.mxproject' ) >/dev/null 2>&1; then
      ( cd "$PROJECT_DIR" && git checkout -- '.mxproject' ) 2>/dev/null \
        && log_info "已 git checkout -- '.mxproject'（避免盘符绝对路径留在工作区）"
    fi
    log_info "回滚后 git status："
    ( cd "$PROJECT_DIR" && git status --porcelain ) >&2 || true
  else
    if "$PYTHON" "${SCRIPT_DIR}/ioc_backup.py" --project "$PROJECT_DIR" --restore >&2; then
      log_info "已从 .ioc.bak 还原"
    else
      log_warn "无 .ioc.bak 可还原；请人工检查 ${PROJECT_DIR}"
    fi
  fi
}

# ---------------------------------------------------------------------------
# 步骤 1：备份
# ---------------------------------------------------------------------------
run_backup() {
  log_info "步骤 1/3：备份 .ioc → .ioc.bak"
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  (dry-run) %s %s --project %s --json-out %s\n' \
      "$PYTHON" "${SCRIPT_DIR}/ioc_backup.py" "$PROJECT_DIR" "$BACKUP_JSON"
    return 0
  fi
  "$PYTHON" "${SCRIPT_DIR}/ioc_backup.py" --project "$PROJECT_DIR" --json-out "$BACKUP_JSON" >&2
}

# ---------------------------------------------------------------------------
# 步骤 2：CubeMX 生成
# ---------------------------------------------------------------------------
run_generate() {
  log_info "步骤 2/3：CubeMX 无头生成（timeout ${TIMEOUT_SEC}s，日志 ${GEN_LOG}）"
  [ -f "$JAVA_BIN" ] || die 2 "找不到 java：$JAVA_BIN（用 --java 或 ST_CUBEMX_JRE 覆盖）"
  [ -f "$CUBE_BIN" ] || die 2 "找不到 CubeMX：$CUBE_BIN（用 --cube 或 ST_CUBEMX_EXE 覆盖）"

  local -a cmd
  if command -v timeout >/dev/null 2>&1; then
    cmd=(timeout "$TIMEOUT_SEC" "$JAVA_BIN" -jar "$CUBE_BIN" -q "$MX_SCRIPT")
  else
    log_warn "找不到 timeout 命令，退化为无超时执行（注意可能长时间挂住）"
    cmd=("$JAVA_BIN" -jar "$CUBE_BIN" -q "$MX_SCRIPT")
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  (dry-run) cd %s && %s > %s 2>&1\n' "$PROJECT_DIR" "${cmd[*]}" "$GEN_LOG"
    return 0
  fi

  # 前置不变量：CubeMX 的 cwd 必须是工程根。
  # 依据：cubemx-generate.mx 里 `config load <相对 .ioc>`，而 CubeMX 默认 cwd 是
  # 安装目录 —— cwd 不对就会去 C:\ST\STM32CubeMX\ 下找死 .ioc。
  local cwd_now
  cwd_now="$( cd "$PROJECT_DIR" && pwd -P )" || die 2 "无法进入工程目录：$PROJECT_DIR"
  [ "$cwd_now" = "$PROJECT_DIR" ] || die 2 "工程根解析不一致（$cwd_now ≠ $PROJECT_DIR），拒绝生成"
  log_info "CubeMX 工作目录：${cwd_now}（脚本内相对 .ioc 路径依赖此 cwd）"

  ( cd "$PROJECT_DIR" && "${cmd[@]}" ) >"$GEN_LOG" 2>&1
  local rc=$?
  log_info "CubeMX 退出码：${rc}（日志 ${GEN_LOG}）"
  return "$rc"
}

# ---------------------------------------------------------------------------
# 步骤 3：核验
# ---------------------------------------------------------------------------
run_verify() {
  log_info "步骤 3/3：生成核验（expect=${EXPECT}，allowlist=${ALLOW_DISPLAY}）"
  local -a args=(
    --log "$GEN_LOG"
    --main-c "$MAIN_C"
    --mxproject "$MXPROJECT"
    --expect "$EXPECT"
    --project-root "$PROJECT_DIR"
    --json-out "$VERIFY_JSON"
    --report-md "$VERIFY_MD"
  )
  local sig
  for sig in ${ALLOW_SIGNALS[@]+"${ALLOW_SIGNALS[@]}"}; do
    [ -n "$sig" ] && args+=(--allow-signal "$sig")
  done

  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  (dry-run) %s %s %s\n' "$PYTHON" "${SCRIPT_DIR}/verify_generation.py" "${args[*]}"
    return 0
  fi
  "$PYTHON" "${SCRIPT_DIR}/verify_generation.py" "${args[@]}"
  return $?
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
run_backup || die 2 "备份 .ioc 失败，未做任何改动"

if [ "$SKIP_GENERATE" -eq 1 ]; then
  log_warn "--skip-generate：跳过 CubeMX 生成，仅核验现有生成物"
else
  if run_generate; then
    :
  else
    GEN_RC=$?
    log_err "CubeMX 生成失败（退出码 ${GEN_RC}）"
    rollback_project
    die 1 "生成失败，已回滚。先看日志：${GEN_LOG}"
  fi
fi

run_verify
VERIFY_RC=$?

if [ "$VERIFY_RC" -ne 0 ]; then
  log_err "生成核验未通过（退出码 ${VERIFY_RC}）：外设可能被静默丢弃，或工程路径不可复现"
  rollback_project
  exit "$VERIFY_RC"
fi

# ---------------------------------------------------------------------------
# 收尾：把 AskForMigrate 复位为 false
# ---------------------------------------------------------------------------
# CubeMX 每次生成/保存都会把该行写回 true（TOOLING §3.3 / D7）。留 true 会让**下一次**
# 生成被上面的前置检查拦死，所以成功路径上必须复位。它只是弹窗开关、不是配置项，
# 用 ioc_field.py 精确改单行（保留 CRLF），不改任何其它字节。
if [ "$RESET_ASK_FOR_MIGRATE" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
  if [ "$("$PYTHON" "${SCRIPT_DIR}/ioc_field.py" --ioc "$IOC_FILE" get ProjectManager.AskForMigrate 2>/dev/null || true)" = "true" ]; then
    log_info "复位 ProjectManager.AskForMigrate → false（否则下一次无头生成会卡在迁移对话框）"
    "$PYTHON" "${SCRIPT_DIR}/ioc_field.py" --ioc "$IOC_FILE" \
      set ProjectManager.AskForMigrate false \
      --json-out "${OUT_DIR}/ioc-normalization.json" >&2 \
      || log_warn "复位 AskForMigrate 失败；下次生成前请手动改成 false"
  fi
fi

cat <<EOF

[regen] 全部通过 ✅
  生成日志   : ${GEN_LOG}
  核验 JSON  : ${VERIFY_JSON}
  核验报告   : ${VERIFY_MD}
  备份快照   : ${BACKUP_JSON}
下一步      : pio run（构建，L3）→ 需要实板再烧录（L5）；提交前按模板 AGENTS.md 写清验证等级
提醒        : 核验器只保证**外设级**（整只外设没被丢）。引脚级增量（如多加一个 PB0）
              不在核验范围，需另加断言：Mcu.PinsNb / __HAL_RCC_GPIOx_CLK_ENABLE() / HAL_GPIO_Init(GPIOx
EOF
exit 0
