#!/usr/bin/env bash
# plugify heartbeat-ctl — 자기 박동 스케줄러 설치/해제/상태/즉시실행 (★2-P2).
#
# ❄ 냉동(2026-07-03 YAGNI 리뷰): uninstall 실행됨. 해동(install) 조건 = 지점 telemetry.sh 실구현.
#
# darwin launchd LaunchAgent 사용(cron 대신): 맥 네이티브 + 슬립 중 놓친 일정을 깨어날 때
# 1회 따라잡음 + 사용자 세션 권한. 매주 월 09:00 heartbeat.sh 발사.
# 되돌리기: `uninstall` (launchctl bootout + plist 삭제) — 완전 가역.
#
# 사용: bash scripts/heartbeat-ctl.sh {install|uninstall|status|run}
set -euo pipefail
HQ="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.plugify.heartbeat"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HEARTBEAT="$HQ/scripts/heartbeat.sh"
DOMAIN="gui/$(id -u)"

write_plist() {
  mkdir -p "$(dirname "$PLIST")" "$HQ/telemetry"
  cat > "$PLIST" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$HEARTBEAT</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>1</integer>
    <key>Hour</key><integer>9</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>$HQ/telemetry/heartbeat.launchd.out</string>
  <key>StandardErrorPath</key><string>$HQ/telemetry/heartbeat.launchd.err</string>
</dict>
</plist>
XML
}

case "${1:-status}" in
  install)
    write_plist
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    launchctl enable "$DOMAIN/$LABEL"
    echo "설치됨: $LABEL (매주 월 09:00) · plist=$PLIST"
    echo "즉시 1회 검증: bash $0 run"
    ;;
  uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "해제됨: $LABEL (plist 삭제)"
    ;;
  run|kickstart)
    launchctl kickstart -k "$DOMAIN/$LABEL"
    echo "kickstart 발사 → 결과: $HQ/telemetry/heartbeat.json"
    ;;
  status)
    if launchctl list 2>/dev/null | grep -q "$LABEL"; then
      echo "launchd: 등록됨 ($LABEL · 매주 월 09:00)"
    else
      echo "launchd: 미등록 — 'install' 로 자기시계 켜기"
    fi
    if [ -f "$HQ/telemetry/heartbeat.json" ]; then
      echo "마지막 박동:"; cat "$HQ/telemetry/heartbeat.json"
    fi
    ;;
  *) echo "사용: $0 {install|uninstall|status|run}"; exit 1;;
esac
