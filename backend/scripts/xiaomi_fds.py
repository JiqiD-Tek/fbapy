# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : xiaomi_fds.py
@Author  : guhua@jiqid.com
@Date    : 2026/09/07

修改说明：
- 仅使用公开 HTTPS 下载（单URL格式），无需尝试多种风格。
- 使用 urllib.parse.quote 进行URL编码，解决特殊字符问题。
- 移除 boto3 依赖，仅依赖 requests 和 FDS SDK（用于管理操作）。
- 保留上传、列表、删除等管理功能（上传不公开）。
"""

import os
import time
import requests
from urllib.parse import quote
from fds.fds_client_configuration import FDSClientConfiguration
from fds.galaxy_fds_client import GalaxyFDSClient
from fds.galaxy_fds_client_exception import GalaxyFDSClientException


class FDSClient(object):

    def __init__(self):
        # 初始化小米 FDS SDK（仅用于上传、列表、删除）
        config = FDSClientConfiguration(
            region_name="cnbj2",
            enable_https=False,
            enable_cdn_for_upload=False,
            enable_cdn_for_download=False,
            endpoint="cnbj2.fds.api.xiaomi.com"
        )
        config.enable_md5_calculate = True
        self.client = GalaxyFDSClient("5771760311796", "RoyKdPxn0BVBI8TVVaFiiw==", config)

    # ---------- 上传 ----------
    def upload_file(self, bucket_name, object_name, data):
        """上传文件（不公开）"""
        self.client.put_object(bucket_name, object_name, data)
        return True

    def upload_local_file(self, bucket_name, object_name, local_file_path):
        """
        上传本地文件到 FDS（不公开）
        :param bucket_name: 桶名
        :param object_name: 对象键名（可含路径）
        :param local_file_path: 本地文件路径
        :return: True 成功
        """
        if not os.path.isfile(local_file_path):
            raise FileNotFoundError(f"本地文件不存在: {local_file_path}")
        with open(local_file_path, 'rb') as f:
            data = f.read()
        return self.upload_file(bucket_name, object_name, data)

    # ---------- 公开 HTTPS 下载（仅单URL） ----------
    def download_object_stream(self, bucket_name, object_name, local_path, retries=3):
        """
        使用公开 HTTPS URL 下载文件（需对象可公开读取）。
        仅使用格式：https://cnbj2.fds.api.xiaomi.com/{bucket_name}/{encoded_object}
        对 object_name 进行 URL 编码，支持中文、空格等特殊字符。
        """
        encoded_object = quote(object_name, safe='/')
        url = f"https://cnbj2.fds.api.xiaomi.com/{bucket_name}/{encoded_object}"

        last_exception = None
        for attempt in range(retries + 1):
            try:
                print(f"尝试下载: {url} (尝试 {attempt+1}/{retries+1})")
                response = requests.get(
                    url,
                    stream=True,
                    timeout=30,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if response.status_code == 200:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"下载成功: {object_name}")
                    return  # 成功返回
                else:
                    print(f"  状态码 {response.status_code}，响应内容: {response.text[:200]}")
                    last_exception = Exception(f"HTTP {response.status_code}")
            except Exception as ex:
                print(f"  请求异常: {ex}")
                last_exception = ex
            time.sleep(2 ** attempt)  # 指数退避重试

        # 所有重试均失败
        raise Exception(f"下载失败（所有尝试）: {object_name}, 最后异常: {last_exception}")

    # ---------- 列表功能（使用 SDK） ----------
    def list_objects(self, bucket_name, prefix='', delimiter=None, max_keys=100):
        return self.client.list_objects(bucket_name, prefix, delimiter, max_keys)

    def list_all_objects(self, bucket_name, prefix='', delimiter=None, max_keys=100):
        all_objects = []
        listing = self.list_objects(bucket_name, prefix, delimiter, max_keys)
        while True:
            all_objects.extend(listing.objects)
            if not listing.is_truncated:
                break
            listing = self.client.list_next_batch_of_objects(listing)
        return all_objects

    def list_all_objects_recursive(self, bucket_name, prefix='', delimiter='/', verbose=False):
        all_objects = []
        current_objects = self.list_all_objects(bucket_name, prefix, delimiter)
        all_objects.extend(current_objects)
        if verbose and current_objects:
            print(f"  [当前层 {prefix}] 找到 {len(current_objects)} 个直接文件")
        prefixes = self._get_all_common_prefixes(bucket_name, prefix, delimiter)
        if verbose:
            print(f"  [前缀 {prefix}] 找到 {len(prefixes)} 个子目录: {prefixes[:5]}...")
        for sub_prefix in prefixes:
            if verbose:
                print(f"  进入子目录: {sub_prefix}")
            all_objects.extend(self.list_all_objects_recursive(bucket_name, sub_prefix, delimiter, verbose))
        return all_objects

    def _get_all_common_prefixes(self, bucket_name, prefix, delimiter='/'):
        all_prefixes = []
        listing = self.list_objects(bucket_name, prefix, delimiter, max_keys=100)
        while True:
            all_prefixes.extend(listing.common_prefixes)
            if not listing.is_truncated:
                break
            listing = self.client.list_next_batch_of_objects(listing)
        return all_prefixes

    def list_all_directories(self, bucket_name, prefix='', delimiter='/'):
        all_dirs = []
        current_dirs = self._get_all_common_prefixes(bucket_name, prefix, delimiter)
        all_dirs.extend(current_dirs)
        for sub in current_dirs:
            all_dirs.extend(self.list_all_directories(bucket_name, sub, delimiter))
        return all_dirs

    def list_all_objects_flat(self, bucket_name, prefix='', max_keys=100):
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

    # ---------- 批量下载 ----------
    def download_all_objects(self, bucket_name, prefix, local_dir='./download_backup/', verbose=True):
        all_objects = self.list_all_objects_recursive(bucket_name, prefix, verbose=verbose)
        if not all_objects:
            print("没有找到任何对象")
            return

        total = len(all_objects)
        print(f"准备下载 {total} 个文件到 {local_dir}")

        failed_list = []
        for idx, obj in enumerate(all_objects, 1):
            object_name = obj.object_name
            rel_path = object_name[len(prefix):] if object_name.startswith(prefix) else object_name
            local_path = os.path.join(local_dir, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            try:
                self.download_object_stream(bucket_name, object_name, local_path)
                if verbose and idx % 100 == 0:
                    print(f"已下载 {idx}/{total}: {object_name}")
            except Exception as e:
                print(f"下载失败 {object_name}: {e}")
                failed_list.append(object_name)

        print(f"下载完成，成功 {total - len(failed_list)} 个，失败 {len(failed_list)} 个。")
        if failed_list:
            print("失败列表（前10个）：", failed_list[:10])


def main():
    fds = FDSClient()
    bucket = "res-center"
    prefix = "qiqi/voice/"

    print("=" * 60)
    print("⚠️  注意：")
    print("1. 本版本仅使用公开 HTTPS 下载，URL格式为：https://cnbj2.fds.api.xiaomi.com/{bucket}/{object}")
    print("2. 请确保桶内文件已公开或使用临时公开链接。")
    print("3. 上传操作不会设置公开权限，文件默认为私有。")
    print("=" * 60)

    # object_key = "qiqi1/voice1/test_upload.txt"  # 上传后的对象键
    # local_test_file = "test_upload.txt"
    # fds.upload_local_file(bucket, object_key, local_test_file)
    # print(f"✅ 上传成功！对象键: {object_key}")

    # fds.download_all_objects(bucket, prefix, local_dir='./backup_qiqi_voice/', verbose=True)

    # 如需删除，取消注释并确认
    confirm = input("确认要删除所有 'qiqi/voice/' 下的数据吗？(yes/no): ")
    if confirm.lower() == 'yes':
        fds.delete_by_prefix(bucket, prefix)
    else:
        print("跳过删除。")


if __name__ == '__main__':
    main()