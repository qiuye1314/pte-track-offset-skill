#!/system/bin/sh
# scripts-install.sh — 把 pte-track-offset-mobile 工具链装到工作区
set -e
SKILL_DIR=$(dirname $(readlink -f "$0"))
WORK=/sdcard/pte_work

echo '=== 安装 PUBG 追踪偏移工具链 ==='
mkdir -p "$WORK" /sdcard/Download/pte_toolkit

# 1. 复制工具
cp "$SKILL_DIR/scripts/pte_track_find.py" "$WORK/" 2>/dev/null || true
cp "$SKILL_DIR/scripts/build_gateway.sh" "$WORK/" 2>/dev/null || true
cp "$SKILL_DIR/scripts/sdk_offset_align.py" "$WORK/" 2>/dev/null || true
chmod +x "$WORK"/*.sh 2>/dev/null || true

echo ''
echo '工具已装到: /sdcard/pte_work/'
ls -la "$WORK"/*.py "$WORK"/*.sh 2>/dev/null || true
echo ''
echo '下一步:'
echo '  1) 拉 so:  adb-shell cp /data/app/*/com.tencent.tmgp.pubgmhd-*/lib/arm64/libUE4.so /sdcard/pte_work/libUE4.so'
echo '  2) 抓偏移: python3 /sdcard/pte_work/pte_track_find.py /sdcard/pte_work/libUE4.so'
echo '  3) 全流程: sh /sdcard/pte_work/build_gateway.sh'
