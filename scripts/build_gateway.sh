#!/system/bin/sh
# ============================================================================
# build_gateway.sh — PUBG 外挂一键构建流水线
#
# 做四件事：
#   1) 从设备拉当前 libUE4.so
#   2) 扫描追踪偏移（特征码），与 SDK 交叉校验
#   3) 自动回填 Offsets.h
#   4) NDK 全量编译 + 链接出可执行文件
#
# 用法:
#   sh build_gateway.sh              # 全流程
#   sh build_gateway.sh --skip-pull  # 跳过拉 so（已有）
#   sh build_gateway.sh --skip-build # 只抓偏移不编译
# ============================================================================
set -e

WORK=/sdcard/pte_work
SRC="$WORK/ex/pte#U8ffd#U9501#U6f0f#U6253#U6e90/jni"
SDK="$WORK/sdk138/#U548c#U5e73SDK"
NDK=/opt/ndk/android-ndk-aide
TC=$NDK/toolchains/llvm/prebuilt/linux-arm
SR=$TC/sysroot
CXX=$TC/bin/clang++
OUT="$WORK/out"
SO="$WORK/libUE4.so"
PKG=com.tencent.tmgp.pubgmhd

SKIP_PULL=0; SKIP_BUILD=0
for a in "$@"; do
  case "$a" in
    --skip-pull) SKIP_PULL=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
  esac
done

say() { echo ""; echo "=== $* ==="; }

# ---------------------------------------------------------------- 1. 拉 so
if [ "$SKIP_PULL" = "0" ]; then
  say "1/4 从设备拉取 libUE4.so"
  APP=$(ls -d /data/app/*/$PKG-*/lib/arm64/libUE4.so 2>/dev/null | head -1)
  if [ -z "$APP" ]; then
    # 容器里看不到，走设备 shell
    echo "  容器内找不到，尝试 adb-shell"
    adb-shell cp "/data/app/~~x4Chc01zhrJd5SC6PW0Jpg==/$PKG-NtWiNgxjVyunlfRIyBIS6w==/lib/arm64/libUE4.so" /sdcard/pte_work/libUE4.so
  else
    cp "$APP" "$SO"
  fi
  ls -la "$SO"
fi

# ---------------------------------------------------------------- 2. 抓偏移
say "2/4 扫描追踪偏移 + SDK 校验"
cd "$WORK"
python3 ue4_track_tool.py "$SO" --sdk "$SDK" --patch "$SRC/include/game/Offsets.h" 2>&1 | tee "$WORK/offset_scan.log"

# ---------------------------------------------------------------- 3. 显示
say "3/4 当前 Offsets.h 关键值"
grep -nE "kTrackShootFn|kGNameAnchor|kWorldAnchor|kMatrixAnchor" "$SRC/include/game/Offsets.h"

# ---------------------------------------------------------------- 4. 编译
if [ "$SKIP_BUILD" = "0" ]; then
  say "4/4 NDK 编译"
  rm -rf "$OUT"; mkdir -p "$OUT/obj" "$OUT/lib"

  INC="-I$SRC/include -I$SRC/src -I$SRC/thirdparty -I$SRC/thirdparty/t3sdk \
       -I$SRC/thirdparty/imgui/include -I$SRC/thirdparty/imgui/include/backends \
       -I$SRC/thirdparty/vulkan_wrapper/include -I$SRC/thirdparty/surface \
       -I$SRC/thirdparty/font -I$SRC/thirdparty/physx/include \
       -I$SRC/src/ui/stormui -I$SRC/src/ui/stormui/pages -I$SRC/src/ui/stormui/widgets \
       -I$SRC/src/ui/stormui/theme -I$SRC/src/ui/stormui/shell -I$SRC/src/ui/stormui/bridge"
  T="--target=aarch64-linux-android21 --sysroot=$SR"
  F="$T -std=c++17 -Wall -fvisibility=hidden -Os -ffunction-sections -fdata-sections \
     -fno-exceptions -fno-rtti -fno-unwind-tables -fno-asynchronous-unwind-tables \
     -D_LIBCPP_DISABLE_AVAILABILITY -DNDEBUG -DVK_USE_PLATFORM_ANDROID_KHR \
     -DIMGUI_IMPL_VULKAN_NO_PROTOTYPES -DIMGUI_DISABLE_DEBUG_TOOLS \
     -DIMGUI_DISABLE_OBSOLETE_FUNCTIONS -DIMGUI_DISABLE_DEMO_WINDOWS"
  FEX="$T -std=c++17 -O2 -Wall -fexceptions -frtti -DNDEBUG"

  echo "  [a] t3auth 静态库"
  for rel in thirdparty/t3sdk/t3sdk.cpp src/core/t3auth_bridge.cpp; do
    n=$(echo $rel | tr '/' '_')
    $CXX $FEX $INC -c "$SRC/$rel" -o "$OUT/obj/t3_$n.o"
  done
  $TC/bin/llvm-ar rcs "$OUT/lib/libt3auth.a" "$OUT"/obj/t3_*.o

  echo "  [b] 主程序目标文件"
  SRCS="src/main.cpp src/core/Log.cpp src/core/Auth.cpp src/core/FrameLoop.cpp
        src/platform/Window.cpp src/render/Renderer.cpp src/render/Font.cpp
        src/input/Touch.cpp src/ui/Panel.cpp
        src/ui/stormui/bridge/bridge.cpp src/ui/stormui/theme/theme.cpp
        src/ui/stormui/theme/icons.cpp src/ui/stormui/shell/state.cpp
        src/ui/stormui/shell/telemetry.cpp src/ui/stormui/widgets/cardui.cpp
        src/ui/stormui/pages/page_home.cpp src/ui/stormui/pages/page_other.cpp
        src/ui/stormui/widgets/widgets.cpp src/ui/stormui/widgets/widgets2.cpp
        src/ui/stormui/shell/sidebar.cpp src/ui/stormui/shell/preview.cpp
        src/ui/stormui/shell/refui.cpp src/ui/stormui/shell/panel.cpp
        src/ui/stormui/shell/pagecommon.cpp src/ui/stormui/pages/page_visuals.cpp
        src/ui/stormui/pages/page_aimbot.cpp src/ui/stormui/pages/page_tracking.cpp
        src/ui/stormui/pages/page_settings.cpp src/config/Config.cpp
        src/config/Features.cpp src/engine/Engine.cpp src/engine/Driver.cpp
        src/engine/ProcMem.cpp src/engine/Session.cpp src/engine/Loader.cpp
        src/engine/Body.cpp src/engine/Aim.cpp src/engine/Track.cpp
        src/engine/PhysX.cpp src/esp/Esp.cpp src/esp/Wts.cpp src/esp/DrawUtil.cpp
        src/render/AndroidImgui.cpp src/render/GraphicsManager.cpp
        src/render/VulkanGraphics.cpp thirdparty/vulkan_wrapper/src/vulkan_wrapper.cpp
        thirdparty/imgui/src/imgui.cpp thirdparty/imgui/src/imgui_draw.cpp
        thirdparty/imgui/src/imgui_tables.cpp thirdparty/imgui/src/imgui_widgets.cpp
        thirdparty/imgui/src/backends/imgui_impl_vulkan.cpp"
  i=0; ok=0; bad=0
  for rel in $SRCS; do
    i=$((i+1))
    if $CXX $F $INC -c "$SRC/$rel" -o "$OUT/obj/m$i.o" 2>"$OUT/obj/m$i.err"; then
      ok=$((ok+1))
    else
      bad=$((bad+1)); echo "  FAIL: $rel"; head -8 "$OUT/obj/m$i.err"
    fi
  done
  echo "  编译: ok=$ok bad=$bad"

  echo "  [c] 链接"
  $CXX $T -fuse-ld=lld -static-libstdc++ \
    -Wl,--gc-sections -Wl,--strip-all -Wl,--as-needed -Wl,-O3 \
    -o "$OUT/fanpian" "$OUT"/obj/m*.o "$OUT/lib/libt3auth.a" \
    -llog -landroid -lz

  ls -la "$OUT/fanpian"
  file "$OUT/fanpian"
  echo ""
  echo "  产物: $OUT/fanpian"
fi

say "完成"
echo "  偏移日志: $WORK/offset_scan.log"
[ "$SKIP_BUILD" = "0" ] && echo "  可执行文件: $OUT/fanpian"
