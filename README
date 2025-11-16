## 介绍

`tiny-make` 是小型的 C++ 构建工具，用途是快速验证 C++ 代码。功能包括：

- 生成项目的 `compile_commands.json`
- 自动检查文件依赖关系
- 编译目标文件并执行

## 动机

需要尽快验证 C++ 代码的正确性，或是写 demo 代码时，文件的依赖关系非常简单，能够自动检查。此时编写 CMake 项目过于繁琐。

## 用途

- 学习 C++ 标准，或学习某个 C++ 库
- 编写自己的库时，需要快速验证代码正确性

## 要求

Python 3.11 及以上版本。

## 示例

进入 `demo` 目录，执行 `python3 ../tiny-make.py main.cpp`。

将自动检查文件依赖关系，生成 `compile_commands.json`，编译并执行 `main.cpp`。

可能的输出如下：

```
$ python3 ../tiny-make.py main.cpp 
executing /usr/bin/clang++-19 -std=c++26 -g -O0 -fno-omit-frame-pointer -Iadd/include -o build/main main.cpp
executing build/main 
1 + 2 = 3
```

## 注意

`tiny-make` 的目的不是代替其他 C++ 构建工具，也不应该用于大型项目。
