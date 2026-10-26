#!/system/bin/sh
# scripts-install.sh — 把 PTE 追踪偏移工具链装到工作区 (v1.5.1)
set -e
SRC=$(dirname $(readlink -f "$0"))
# SRC 可能是 scripts/ 本身, 也可能是 skill 根目录
if [ -f "$SRC/export_baseline.py" ]; then S="$SRC"; else S="$SRC/scripts"; fi
DATA=$(dirname "$S")/data
WORK=/sdcard/pte_work

echo '=== 安装 PTE 追踪偏移工具链 v1.5.1 ==='
mkdir -p "$WORK" /sdcard/Download/pte_toolkit

for f in ue4_track_tool.py pte_track_find.py export_baseline.py diff_baseline.py sdk_offset_align.py offset_fix_table.py sdk_verify2.py build_gateway.sh detect_source_target.py bump_version.py; do
  if [ -f "$S/$f" ]; then cp "$S/$f" "$WORK/" && echo "  + $f"; fi
done
if [ -d "$DATA" ]; then
  for f in "$DATA"/baseline_*.json "$DATA"/PTE_BASELINE_*.md; do
    [ -f "$f" ] && cp "$f" "$WORK/" && echo "  + $(basename $f)"
  done
fi
chmod +x "$WORK"/*.sh 2>/dev/null || true

echo ''
echo '已装到: /sdcard/pte_work/'
echo ''
echo '常用:'
echo '  抓偏移(只读): python3 $WORK/ue4_track_tool.py $WORK/libUE4.so --sdk /sdcard'
echo '  导基线:       python3 $WORK/export_baseline.py $WORK/libUE4.so --sdk-dir <SDK> --offsets <Offsets.h> --out $WORK/baseline_now.json'
echo '  新赛季对撞:   python3 $WORK/diff_baseline.py --base $WORK/baseline_1.38.12.json --new $WORK/baseline_now.json'
echo '  全流程:       sh $WORK/build_gateway.sh'
echo '  判归属:       python3 $WORK/detect_source_target.py <工程目录>'
echo '  看文档:       pte_track_doc(section="attrib" / "intl46")'
