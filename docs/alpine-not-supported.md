# Why Alpine Linux Is Not Supported

## TL;DR

**Alpine Linux cannot be used for this project due to tree-sitter compilation failures on arm64/aarch64 architecture.**

---

## Technical Background

### The Problem

The `tree-sitter` Python package (a dependency of StrictDoc) has **hardcoded Clang compiler flags** that are incompatible with Alpine Linux's toolchain:

```python
# From tree-sitter Python package source
extra_compile_args=['-std=c99', '--rtlib=compiler-rt']
```

### Why This Breaks on Alpine

1. **Alpine uses musl libc** instead of glibc
2. **Alpine's default compiler is GCC**, which doesn't recognize `--rtlib=compiler-rt`
3. **No pre-built musl wheels** exist for tree-sitter on arm64/aarch64 architecture
4. **Forces compilation from source**, which triggers the incompatible compiler flags

### Error Message

```
building 'tree_sitter.binding' extension
gcc -Wsign-compare -DNDEBUG -g -fwrapv -O3 -Wall -Os -fstack-clash-protection
-Wformat -Werror=format-security -fno-plt -fPIC -std=c99 --rtlib=compiler-rt
-I/root/.local/share/uv/python/cpython-3.13.1-linux-aarch64-musl/include/python3.13
-c tree_sitter/binding.c -o build/tree_sitter/binding.o

cc: error: unrecognized command-line option '--rtlib=compiler-rt'
error: command 'gcc' failed with exit code 1
```

---

## Attempted Solutions (All Failed)

### 1. ❌ Use GCC (Default Alpine Compiler)

**Dockerfile.alpine:**
```dockerfile
FROM alpine:3.19
RUN apk add --no-cache gcc musl-dev libffi-dev
```

**Result:** GCC doesn't support `--rtlib=compiler-rt` flag

---

### 2. ❌ Install Clang Instead of GCC

**Dockerfile.alpine-clang:**
```dockerfile
FROM alpine:3.19
RUN apk add --no-cache clang clang-dev llvm
ENV CC=clang CXX=clang++
```

**Result:** Clang recognizes the flag but compiler-rt library not available in Alpine

---

### 3. ❌ Add glibc Compatibility Layer

**Dockerfile.alpine-glibc:**
```dockerfile
FROM alpine:3.19
RUN wget https://github.com/sgerrand/alpine-pkg-glibc/releases/download/${GLIBC_VERSION}/glibc-${GLIBC_VERSION}.apk
RUN apk add --no-cache --force-overwrite glibc-${GLIBC_VERSION}.apk
```

**Result:** Still requires compilation (no pre-built wheels for arm64), same GCC/Clang issues

---

### 4. ❌ Multi-stage Build: Compile on Debian, Run on Alpine

**Dockerfile.alpine-multistage:**
```dockerfile
# Builder stage - Debian (glibc)
FROM debian:bookworm-slim AS builder
RUN uv sync --frozen --no-dev

# Runtime stage - Alpine (musl)
FROM alpine:3.19
COPY --from=builder /root/.local/share/uv/python /opt/python
COPY --from=builder /app/.venv /app/.venv
```

**Result:** **Fundamental incompatibility** - Python binaries compiled with glibc cannot run on musl libc

---

## Why Pre-built Wheels Don't Help

### Wheel Availability by Platform:

| Platform | Architecture | Wheels Available? |
|----------|--------------|-------------------|
| **glibc (Debian, UBI)** | x86_64 | ✅ Yes |
| **glibc (Debian, UBI)** | aarch64 | ✅ Yes |
| **musl (Alpine)** | x86_64 | ✅ Yes |
| **musl (Alpine)** | **aarch64** | ❌ **NO** |

**Our deployment target:** arm64/aarch64 architecture

**Conclusion:** No pre-built wheels → forced compilation → compiler flag failure

---

## The Solution: Red Hat UBI

### Why UBI Works:

1. ✅ **Uses glibc** (same as Debian)
2. ✅ **Pre-built wheels available** for arm64/aarch64
3. ✅ **No compilation needed** for tree-sitter
4. ✅ **Fast dependency installation** (milliseconds vs minutes)
5. ✅ **Enterprise support and security** from Red Hat
6. ✅ **OpenShift compatible** out of the box

### Size Comparison:

| Base Image | Size | Build Time* | Status |
|------------|------|-------------|--------|
| **Red Hat UBI 9** | **604MB** | Fast (cached) | ✅ **Production** |
| Debian Bookworm | 749MB | Fast (cached) | ✅ Working |
| Alpine 3.19 | N/A | Failed | ❌ **Blocked** |

*With uv cache mounts and pre-compiled wheels

---

## Could This Be Fixed in the Future?

### Possible But Unlikely:

1. **tree-sitter upstream fix**: Remove hardcoded Clang flags
   - Would require maintainer action
   - Breaking change for some users
   - No timeline for this

2. **Pre-built musl wheels for arm64**: Community could provide
   - Requires someone to build and distribute
   - Maintenance overhead
   - No indication this will happen

3. **Alpine adds compiler-rt**: Unlikely
   - Alpine philosophy favors GCC
   - Clang support is minimal
   - Not a priority for Alpine maintainers

### Monitoring:

Check these occasionally for changes:
- https://github.com/tree-sitter/py-tree-sitter/issues
- https://pypi.org/project/tree-sitter/#files (wheel availability)
- Alpine package repositories for compiler-rt support

---

## Recommendations for Similar Projects

### If You Need Alpine:

1. **Check dependencies first**: Look for C extensions with Alpine compatibility issues
2. **Test on target architecture**: x86_64 may work when arm64 doesn't
3. **Have a fallback**: UBI or Debian as alternative base images
4. **Consider multi-arch**: Use Alpine for x86_64, UBI for arm64

### Red Flags for Alpine Compatibility:

- ❌ Dependencies with C extensions (cryptography, lxml, tree-sitter)
- ❌ Packages requiring specific compiler versions
- ❌ arm64/aarch64 deployment target without pre-built musl wheels
- ❌ Packages with hardcoded glibc dependencies

### When Alpine Works Well:

- ✅ Pure Python applications (no C extensions)
- ✅ x86_64 architecture only
- ✅ Dependencies with pre-built musl wheels
- ✅ Static binaries (Go, Rust applications)

---

## References

### Tested Configurations:

- **Dockerfile.alpine** - Alpine 3.19 with GCC
- **Dockerfile.alpine-clang** - Alpine 3.19 with Clang
- **Dockerfile.alpine-glibc** - Alpine 3.19 with glibc compatibility
- **Dockerfile.alpine-multistage** - Multi-stage Debian→Alpine

All configurations tested on:
- **Architecture:** arm64/aarch64 (Apple Silicon)
- **Docker:** Docker Desktop with BuildKit enabled
- **Python:** 3.13.7
- **tree-sitter:** 0.23.2 (via StrictDoc dependency)

### Build Logs:

See `BASE_IMAGE_COMPARISON.md` for detailed test results and error logs.

---

## Conclusion

**Alpine Linux is not viable for this project** due to fundamental incompatibilities:
- tree-sitter requires compilation on arm64 Alpine
- Hardcoded Clang flags incompatible with Alpine's GCC
- No Alpine compiler-rt library available
- Multi-stage workarounds fail due to glibc/musl incompatibility

**Red Hat UBI 9 is the recommended solution**, providing:
- Pre-compiled wheels (fast builds)
- Smaller image than Debian (604MB vs 749MB)
- Enterprise support and security
- Full compatibility with project dependencies

---

**Last Updated:** 2025-10-07
**Tested On:** Docker Desktop (macOS arm64), Python 3.13.7, StrictDoc 0.10.0
