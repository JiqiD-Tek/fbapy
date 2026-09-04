# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : xiaomi_fds.py
@Author  : guhua@jiqid.com
@Date    : 2026/09/04 09:28
"""
from fds.fds_client_configuration import FDSClientConfiguration
from fds.galaxy_fds_client import GalaxyFDSClient


class FDSClient(object):

    def __init__(self):
        config = FDSClientConfiguration(
            region_name="cnbj2",
            enable_https=False,
            enable_cdn_for_upload=False,
            enable_cdn_for_download=False,
            endpoint="cnbj2.fds.api.xiaomi.com")
        config.enable_md5_calculate = True
        self.client = GalaxyFDSClient("5771760311796", "RoyKdPxn0BVBI8TVVaFiiw==", config)

    # ---------- 上传 / 下载 ----------
    def upload_file(self, bucket_name, object_name, data):
        self.client.put_object(bucket_name, object_name, data)
        self.client.set_public(bucket_name, object_name)
        return True

    def download_file(self, bucket_name, object_name, file_name):
        return self.client.download_object(bucket_name, object_name, file_name)

    # ---------- 列表（官方推荐方式） ----------
    def list_objects(self, bucket_name, prefix='', delimiter=None, max_keys=100):
        return self.client.list_objects(bucket_name, prefix, delimiter, max_keys)

    def list_all_objects(self, bucket_name, prefix='', delimiter=None, max_keys=100):
        """
        自动分页，返回当前前缀下的所有对象（不递归子目录）。
        """
        all_objects = []
        listing = self.list_objects(bucket_name, prefix, delimiter, max_keys)
        while True:
            all_objects.extend(listing.objects)
            if not listing.is_truncated:
                break
            listing = self.client.list_next_batch_of_objects(listing)
        return all_objects

    # ---------- 递归列出所有子目录中的对象（显式递归） ----------
    def list_all_objects_recursive(self, bucket_name, prefix='', delimiter='/', verbose=False):
        """
        递归列出所有对象（包括子目录），返回 FDSObjectSummary 列表。
        如果 verbose=True，会打印每个子目录的扫描进度。
        """
        all_objects = []

        # 1. 获取当前层的直接文件
        current_objects = self.list_all_objects(bucket_name, prefix, delimiter)
        all_objects.extend(current_objects)
        if verbose and current_objects:
            print(f"  [当前层 {prefix}] 找到 {len(current_objects)} 个直接文件")

        # 2. 获取所有子目录（common_prefixes）
        prefixes = self._get_all_common_prefixes(bucket_name, prefix, delimiter)
        if verbose:
            print(f"  [前缀 {prefix}] 找到 {len(prefixes)} 个子目录: {prefixes[:5]}...")

        # 3. 递归进入每个子目录
        for sub_prefix in prefixes:
            if verbose:
                print(f"  进入子目录: {sub_prefix}")
            all_objects.extend(self.list_all_objects_recursive(bucket_name, sub_prefix, delimiter, verbose))

        return all_objects

    def _get_all_common_prefixes(self, bucket_name, prefix, delimiter='/'):
        """获取指定前缀下的所有子目录（自动分页）"""
        all_prefixes = []
        listing = self.list_objects(bucket_name, prefix, delimiter, max_keys=100)
        while True:
            all_prefixes.extend(listing.common_prefixes)
            if not listing.is_truncated:
                break
            listing = self.client.list_next_batch_of_objects(listing)
        return all_prefixes

    # ========== 🆕 新增：展示所有目录（递归） ==========
    def list_all_directories(self, bucket_name, prefix='', delimiter='/'):
        """
        递归列出所有子目录（common_prefixes），返回目录路径列表（末尾带斜杠）。
        此方法只返回目录，不包含文件。
        """
        all_dirs = []
        # 获取当前层的所有子目录
        current_dirs = self._get_all_common_prefixes(bucket_name, prefix, delimiter)
        all_dirs.extend(current_dirs)
        # 递归进入每个子目录继续查找
        for sub in current_dirs:
            all_dirs.extend(self.list_all_directories(bucket_name, sub, delimiter))
        return all_dirs

    # ---------- 递归列出所有对象（方式二：扁平，一次性获取） ----------
    def list_all_objects_flat(self, bucket_name, prefix='', max_keys=100):
        """
        使用 delimiter=None 一次性列出所有对象（包括深层），无需递归。
        注意：如果对象数量巨大（>10万），可能较慢，但简单可靠。
        """
        return self.list_all_objects(bucket_name, prefix, delimiter=None, max_keys=max_keys)

    # ---------- 删除 ----------
    def delete_object(self, bucket_name, object_name):
        return self.client.delete_object(bucket_name, object_name)

    def delete_objects(self, bucket_name, object_names):
        failed = []
        for name in object_names:
            try:
                self.delete_object(bucket_name, name)
            except Exception as e:
                failed.append((name, str(e)))
        return failed

    def delete_by_prefix(self, bucket_name, prefix, delimiter='/'):
        all_objects = self.list_all_objects_recursive(bucket_name, prefix, delimiter)
        if not all_objects:
            print(f"没有找到前缀为 '{prefix}' 的对象")
            return
        object_names = [obj.object_name for obj in all_objects]
        print(f"准备删除 {len(object_names)} 个对象...")
        failed = self.delete_objects(bucket_name, object_names)
        if failed:
            print(f"删除失败 {len(failed)} 个：{failed}")
        else:
            print("全部删除成功。")


def main():
    fds = FDSClient()
    bucket = "res-center"
    prefix = "qiqi/voice/"

    # ========== 新增：展示所有目录 ==========
    print("=== 所有目录（递归） ===")
    all_dirs = fds.list_all_directories(bucket, prefix)
    print(f"共找到 {len(all_dirs)} 个目录")
    for d in all_dirs[:10]:  # 只显示前10个
        print(f"  {d}")

    # ========== 递归列出所有文件（带调试输出） ==========
    print("\n=== 递归列出所有文件（带调试输出） ===")
    all_files = fds.list_all_objects_recursive(bucket, prefix, verbose=True)
    print(f"\n递归共找到 {len(all_files)} 个文件")
    for obj in all_files[:5]:
        print(f"  {obj.object_name} ({obj.size} bytes)")

    # ========== 扁平列出所有对象 ==========
    print("\n=== 使用 delimiter=None 扁平列出所有对象 ===")
    flat_files = fds.list_all_objects_flat(bucket, prefix)
    print(f"扁平共找到 {len(flat_files)} 个文件")
    for obj in flat_files[:5]:
        print(f"  {obj.object_name} ({obj.size} bytes)")

    # 删除示例（谨慎使用）
    # fds.delete_by_prefix(bucket, "qiqi/voice/2019-07-31/")


if __name__ == '__main__':
    main()