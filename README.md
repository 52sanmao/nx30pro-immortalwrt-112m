# H3C Magic NX30 Pro —— ImmortalWrt 112M 大分区自编译

在 GitHub Actions 云端把 **官方 ImmortalWrt** 编译成「112M 大分区」版本，
配合 Yuzhii U-Boot 的 `immortalwrt-112m` 布局使用。

## 为什么官方没有 112M

官方 `mt7981b-h3c-magic-nx30-pro.dts` 里 `ubi` 是 `0x4000000`（64M），
剩下 50.5MB 被 `pdt_data` / `pdt_data_1` / `exp` / `plugin` 四个原厂只读分区占着。
官方适配一律不做大分区（据 hanwckf 说明，这台机器名义 128MB 闪存但可能有坏块）。

## 本仓库做了什么

`scripts/enable_112m.py` 在编译前对源码做两处修改：

| 文件 | 改动 |
|---|---|
| `target/linux/mediatek/dts/mt7981b-h3c-magic-nx30-pro.dts` | `ubi` 从 `0x4000000`(64M) 改为 `0x7000000`(112M)，并删除被它覆盖的 `pdt_data` / `pdt_data_1` / `exp` / `plugin` 四个节点 |
| `target/linux/mediatek/image/filogic.mk` | 该设备 `IMAGE_SIZE` 从 `65536k` 改为 `114688k`（否则打包时 check-size 会拦） |

改完的分区布局与 Yuzhii U-Boot 内置的 `immortalwrt-112m` 完全对应：

```
nmbm0:1024k(bl2),512k(u-boot-env),2048k(Factory),2048k(fip),112M(ubi)
```

`Factory`（RF 校准）与 `u-boot-env` 都保留，不动。

## 怎么用

1. 仓库 **Actions** → `build-immortalwrt-112m` → **Run workflow**
2. `tag` 填要编的版本（默认 `v25.12.2`），`extra_packages` 可留空
3. 约 1.5–3 小时，跑完在 **Artifacts** 里下载 `immortalwrt-112m-<tag>`

产物说明：

| 文件 | 用途 |
|---|---|
| `*-squashfs-sysupgrade.itb` | 正常刷机镜像（**要用这个**） |
| `*-initramfs-recovery.itb` | 内存恢复镜像，切换布局时用它进 initramfs 再 sysupgrade |
| `*-bl31-uboot.fip` / `*-preloader.bin` | 官方引导器，**已在用 Yuzhii 的话不要刷** |
| `112m-changes.diff` | 本次编译对源码的完整改动，可复核 |

## 刷之前必须知道

- **布局和数据是一次性切换**：切到 112M 后，原 ubi 里的系统与配置会全部清空，
  必须 `sysupgrade -n`（不保留配置）刷入新固件。
- **`pdt_data` 里有原厂 jffs2 内容**，合并进 ubi 就没了。要留底就先整块备份
  （6M × 2）。
- 刷之前先在 U-Boot 网页里确认布局切到了 `immortalwrt-112m`；
  在旧布局下刷 112M 固件会因为分区重叠而失败。
