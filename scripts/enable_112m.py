#!/usr/bin/env python3
"""
把 ImmortalWrt 官方 NX30 Pro 适配改成 112M 大分区（对应 Yuzhii U-Boot 的
immortalwrt-112m 布局）。

布局（Yuzhii FIP 内置）：
  nmbm0:1024k(bl2),512k(u-boot-env),2048k(Factory),2048k(fip),112M(ubi)
即 ubi 从 0x580000 开始，长度 0x7000000。

改动两处：
  1. DTS: ubi 0x4000000 -> 0x7000000，并删除被覆盖的 pdt_data / pdt_data_1 /
     exp / plugin 四个只读分区节点
  2. filogic.mk: 该设备 IMAGE_SIZE 65536k -> 114688k（否则 check-size 会拦）
"""
import re
import sys
import pathlib

LABELS_TO_DROP = {"pdt_data", "pdt_data_1", "exp", "plugin"}
UBI_OLD = "reg = <0x0580000 0x4000000>;"
UBI_NEW = "reg = <0x0580000 0x7000000>;"
UBI_END = 0x0580000 + 0x7000000

DEV = "h3c_magic-nx30-pro"


def find_dts(root: pathlib.Path) -> pathlib.Path:
    d = root / "target/linux/mediatek/dts"
    for name in ("mt7981b-h3c-magic-nx30-pro.dts", "mt7981-h3c-magic-nx30-pro.dts"):
        p = d / name
        if p.exists():
            return p
    sys.exit("ERROR: NX30 Pro DTS 未找到于 %s" % d)


def strip_partitions(text: str, labels: set) -> tuple[str, list]:
    lines = text.split("\n")
    out, removed = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\s*)partition@([0-9a-f]+)\s*\{\s*$", line)
        if not m:
            out.append(line)
            i += 1
            continue
        block = [line]
        j = i + 1
        while j < len(lines) and lines[j].strip() != "};":
            block.append(lines[j])
            j += 1
        if j < len(lines):
            block.append(lines[j])
            j += 1
        body = "\n".join(block)
        lab = re.search(r'label\s*=\s*"([^"]+)"', body)
        if lab and lab.group(1) in labels:
            removed.append(lab.group(1))
            while out and re.fullmatch(r"\s*/\*.*\*/\s*", out[-1]):
                out.pop()
            if j < len(lines) and lines[j].strip() == "":
                j += 1
            i = j
            continue
        out.extend(block)
        i = j
    return "\n".join(out), removed


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: enable_112m.py <openwrt-source-root>")
    root = pathlib.Path(sys.argv[1]).resolve()

    # ---------- 1. DTS ----------
    dts = find_dts(root)
    s = dts.read_text(encoding="utf-8")
    if UBI_NEW in s:
        print("DTS 已是 112M，跳过")
    else:
        if UBI_OLD not in s:
            sys.exit("ERROR: %s 里没找到 %s" % (dts, UBI_OLD))
        s = s.replace(UBI_OLD, UBI_NEW, 1)
        s, removed = strip_partitions(s, LABELS_TO_DROP)
        missing = LABELS_TO_DROP - set(removed)
        if missing:
            sys.exit("ERROR: 这些分区没被删掉: %s" % sorted(missing))
        dts.write_text(s, encoding="utf-8", newline="\n")
        print("DTS 已改: %s (删除 %s)" % (dts.name, sorted(removed)))

    # 校验：不应再有落在 ubi 范围内的分区
    for m in re.finditer(r"partition@([0-9a-f]+)\s*\{([^}]*)\}", s):
        off = int(m.group(1), 16)
        lab = re.search(r'label\s*=\s*"([^"]+)"', m.group(2))
        name = lab.group(1) if lab else "?"
        if 0x0580000 < off < UBI_END:
            sys.exit("ERROR: 分区 %s@0x%x 仍落在 ubi 范围内" % (name, off))
    print("DTS 校验通过: ubi = 0x7000000 (112M), 结束于 0x%x" % UBI_END)

    # ---------- 2. filogic.mk ----------
    mk = root / "target/linux/mediatek/image/filogic.mk"
    t = mk.read_text(encoding="utf-8")
    m = re.search(r"define Device/%s\n(.*?)\nendef" % re.escape(DEV), t, re.S)
    if not m:
        sys.exit("ERROR: filogic.mk 里没找到 Device/%s" % DEV)
    body = m.group(1)
    if "IMAGE_SIZE := 114688k" in body:
        print("filogic.mk 已是 114688k，跳过")
    else:
        if "IMAGE_SIZE := 65536k" not in body:
            sys.exit("ERROR: Device/%s 里没找到 IMAGE_SIZE := 65536k" % DEV)
        new_body = body.replace("IMAGE_SIZE := 65536k", "IMAGE_SIZE := 114688k")
        t = t[: m.start(1)] + new_body + t[m.end(1):]
        mk.write_text(t, encoding="utf-8", newline="\n")
        print("filogic.mk 已改: Device/%s IMAGE_SIZE = 114688k" % DEV)

    # ---------- 3. 复核 ----------
    d2 = find_dts(root).read_text(encoding="utf-8")
    t2 = mk.read_text(encoding="utf-8")
    assert UBI_NEW in d2, "DTS 复核失败"
    blk = re.search(r"define Device/%s\n(.*?)\nendef" % re.escape(DEV), t2, re.S).group(1)
    assert "IMAGE_SIZE := 114688k" in blk, "filogic.mk 复核失败"
    for lab in LABELS_TO_DROP:
        assert ('label = "%s"' % lab) not in d2, "分区 %s 仍在" % lab
    print("全部复核通过：可以开始编译")


if __name__ == "__main__":
    main()
