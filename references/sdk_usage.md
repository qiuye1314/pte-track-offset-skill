# UE4Dump SDK 用法与边界

## 一、SDK 文件构成（UE4Dump 标准输出）

| 文件 | 典型大小 | 内容 |
|---|---|---|
| Offsets.hpp | 2~3KB | 引擎锚点 + 核心结构偏移 |
| AIOHeader.hpp | 30~35MB | 全部类定义（成员带 // 0x偏移） |
| Objects.txt | 60~65MB | 对象/类/函数名单 |
| script.json | 7~8MB | 函数地址 + 名字（IDA 脚本） |
| Logs.txt | 2~3KB | dump 时的内存映射 + 实测结果 |

## 二、SDK 收录范围（关键认知）

```
script.json 收录的 60020 个函数，100% 是 "$$exec" 结尾
$$exec = UFunction 的 ProcessEvent 反射跳板
→ 只有注册进 UObject 反射系统的函数才会被收录
→ 原生 C++ 虚函数（如追踪桩）不注册 → 收不到
```

**验证方法**：
```bash
python3 -c "
import json
d=json.load(open('script.json'))
fns=[f for f in d['Functions'] if f]
ec=sum(1 for f in fns if '$$exec' in f['Name'])
print('总数 %d, exec %d (%.1f%%)' % (len(fns), ec, 100.0*ec/len(fns)))
"
# 输出: 总数 59992, exec 59992 (100.0%)
```

## 三、SDK 能查什么

### 3.1 引擎锚点（Offsets.hpp）

```cpp
namespace UEPointers {
    Names         = 0x16CA0898;   // GNames 池
    UObjectArray  = 0x173EE2B8;   // GUObjectArray
    ObjObjects    = 0x173EE2C8;
    Engine        = 0x17719B78;   // GEngine
    World         = 0x1771CC38;   // GWorld
}
```

**直接抄进工程**，但必须先用锚点对照验证 build 一致。

### 3.2 类字段偏移（AIOHeader.hpp）

格式：
```cpp
struct ASTExtraCharacter : AUAECharacter
{
    struct FSomething SomeField;  // 0x1060(0x4)
    float Health;                 // 0x1060(0x4)
}
```

搜索方式：
```bash
# 找类定义
grep -n '^struct ASTExtraBaseCharacter' AIOHeader.hpp

# 看某类全部成员（从类定义往下抓）
awk '/^struct AActor : /{f=1} f{print NR": "$0; c++} c>60{exit}' AIOHeader.hpp
```

### 3.3 类继承关系

```bash
grep -n '^struct ASTExtraBaseCharacter' AIOHeader.hpp
# 输出: 165900:struct ASTExtraBaseCharacter : ASTExtraCharacter
#       → 继承链 ASTExtraBaseCharacter -> ASTExtraCharacter -> AUAECharacter
#                 -> ACharacter -> APawn -> AActor -> UObject
```

**重要**：字段可能定义在父类里，查找时必须**沿继承链向上找**。

## 四、SDK 不能查什么

| 查不到的东西 | 原因 | 替代方案 |
|---|---|---|
| 追踪桩（kTrackShootFn） | 原生虚函数，不在反射表 | 特征码 + 虚表反查 |
| 其它原生 C++ 虚函数 | 同上 | 同上 |
| 静态函数地址 | 不在 UFunction 表 | 特征码 / IDA |
| 加密字段的真实值 | SDK 只有结构 | 动态调试 |

## 五、偏移校准工作流

```python
# 1. 解析工程的偏移
plugin = {k: v for k, v in re.findall(r'k(\w+)\s*=\s*(0x[0-9A-Fa-f]+)', src)}

# 2. 解析 SDK 的类成员
# 每行形如:  <type> <name>; // 0x<off>(0x<size>)

# 3. 沿继承链查找该偏移
def lookup(cls, off):
    for c in chain(cls):          # 继承链向上
        for o, n, t in CLS[c]['members']:
            if o == off: return c, n, t
    return None

# 4. 判定
#    命中 + 名字语义吻合 → OK
#    命中 + 名字不吻合   → ?? 存疑
#    未命中              → 查全局 BYOFF 索引
```

## 六、PUBG 1.38.12 实测结果

**锚点一致性**：5/5（Names/World/Engine/UObjectArray/ObjObjects）→ 同一 build

**偏移命中率**：27/34 精确命中，字段名语义全吻合

**抓出的错误偏移**：
| 常量 | 工程值 | SDK 实际 | 修正建议 |
|---|---|---|---|
| kActorHeight | 0x10BC | DefaultSpeedValue | → 0x3E70 StandHalfHeight |
| kActorFeature | 0x3B9C | HighWalkSpeed | → 0x1D78 InheritFeatureComs |
| kActorAimVector | 0x1164 | VelocitySafety | → 需人工确认 |

**关键类字段数**（可用于估算结构复杂度）：
```
AActor                   137 字段
ACharacter                47 字段
ASTExtraCharacter        225 字段
ASTExtraBaseCharacter   1001 字段
ASTExtraPlayerController 1161 字段
ASTExtraGameStateBase    491 字段
ASTExtraShootWeapon      331 字段
```
