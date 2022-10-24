#!/usr/bin/python3
# -*- coding:utf-8 -*-
# @Author  : gty0211@foxmail.com, cgc.elvom@outlook.com

import json
import os
import sys
import shutil
import ffmpeg
import piexif
import hashlib
from PIL import Image, UnidentifiedImageError
from datetime import datetime
from tqdm import tqdm

# 归档zip解压目录
scanDir = ''
outPutDir = ''


class DealGooglePhotosArchive(object):

    def __init__(self, scanDir: str) -> None:
        self.scanDir = scanDir
        self.outPutDir = self.check()
        self.DupDir = os.path.join(self.outPutDir, 'Duplicate')  # 重复文件存放文件夹
        self.under2Dir = os.path.join(self.outPutDir, 'under2')
        self.under3Dir = os.path.join(self.outPutDir, 'under3')
        self.heicDir = os.path.join(self.outPutDir, 'HEIC')
        self.jsonDir = os.path.join(self.outPutDir, 'json')
        self.photosDir = os.path.join(self.outPutDir, 'Photos')

    def GetMD5FromFile(self, filename):
        """获取文件MD5

        Args:
            filename (_type_): _description_

        Returns:
            _type_: _description_
        """        
        file_object = open(filename, 'rb')
        file_content = file_object.read()
        file_object.close()
        file_md5 = hashlib.md5(file_content)
        return file_md5.hexdigest()


    def dealDuplicate(self, delete=True):
        """处理重复

        Args:
            delete (bool, optional): _description_. Defaults to True.
        """
        fileMD5List = {}
        dg = os.walk(scanDir)
        
        if not os.path.exists(self.DupDir):
            os.makedirs(self.DupDir)

        for path, _, file_list in dg:
            if path == self.DupDir:
                print('跳过 '+self.DupDir+' 文件夹')
                continue
            for file_name in tqdm(file_list, desc="dealDuplicate"):
                full_file_name = os.path.join(path, file_name)
                if file_name == '元数据.json':
                    continue
                # 处理重复文件
                _md5 = self.GetMD5FromFile(full_file_name)
                if _md5 in fileMD5List.keys() and full_file_name != fileMD5List[_md5]:
                    if delete:
                        os.remove(full_file_name)  # 这里可以直接删除
                    else:
                        if not os.path.exists(self.DupDir + file_name):
                            shutil.move(full_file_name, self.DupDir)
                        else:  # 存在多个就删除
                            os.remove(full_file_name)
                    print('重复文件：' + full_file_name +
                        ' ------ ' + fileMD5List[_md5])
                else:
                    fileMD5List[_md5] = full_file_name
        fileMD5List.clear()


    def dealClassify(self):
        """文件分类
        """
        # 部分文件变了，重新扫描
        g = os.walk(scanDir)
        for path, _, file_list in g:
            for file_name in tqdm(file_list, desc="dealClassify"):
                full_file_name = os.path.join(path, file_name)
                # 处理时长低于3s的视频
                if os.path.splitext(file_name)[-1] == '.MOV':
                    print('根据时长分类文件：' + full_file_name)
                    info = ffmpeg.probe(full_file_name)
                    # print(info)
                    duration = info['format']['duration']  # 时长
                    if float(duration) <= 2:
                        
                        if not os.path.exists(self.under2Dir):
                            print('创建文件夹：' + self.under2Dir)
                            os.makedirs(self.under2Dir)
                        if not os.path.exists(self.under2Dir + file_name):
                            shutil.move(full_file_name, self.under2Dir)

                    elif 2 < float(duration) <= 3:
                        
                        if not os.path.exists(self.under3Dir):
                            print('创建文件夹：' + self.under3Dir)
                            os.makedirs(self.under3Dir)
                        if not os.path.exists(self.under3Dir + file_name):
                            shutil.move(full_file_name, self.under3Dir)
                # 处理HEIC文件
                elif os.path.splitext(file_name)[-1] == '.HEIC':
                    
                    if not os.path.exists(self.heicDir):
                        os.makedirs(self.heicDir)
                    if not os.path.exists(self.heicDir + file_name):
                        shutil.move(full_file_name, self.heicDir)
                # 单独存储json文件
                elif os.path.splitext(file_name)[-1] == '.json':
                    
                    if not os.path.exists(self.jsonDir):
                        os.makedirs(self.jsonDir)
                    if not os.path.exists(self.jsonDir + file_name):
                        shutil.move(full_file_name, self.jsonDir)
                # 其他文件存储到Photos文件夹
                else:
                    
                    if not os.path.exists(self.photosDir):
                        os.makedirs(self.photosDir)
                    if not os.path.exists(self.photosDir + file_name):
                        shutil.move(full_file_name, self.photosDir)


    # 计算lat/lng信息
    def format_latlng(self, latlng):
        degree = int(latlng)
        res_degree = latlng - degree
        minute = int(res_degree * 60)
        res_minute = res_degree * 60 - minute
        seconds = round(res_minute * 60.0, 3)

        return ((degree, 1), (minute, 1), (int(seconds * 1000), 1000))


    # 读json
    def readJson(self, json_file):
        with open(json_file, 'r', encoding='UTF-8') as load_f:
            return json.load(load_f)


    def dealExif(self):
        """处理照片exif信息
        """
        g = os.walk(scanDir)
        for path, _, file_list in g:
            for file_name in tqdm(file_list, desc="dealExif"):
                full_file_name = os.path.join(path, file_name)
                ext_name = os.path.splitext(file_name)[-1]
                if ext_name.lower() in ['.jpg', '.jpeg', '.png']:

                    if os.path.exists(os.path.join(self.jsonDir, file_name + '.json')):
                        exifJson = self.readJson(os.path.join(
                            self.jsonDir, file_name + '.json'))
                        print('处理Exif：' + full_file_name)
                        try:
                            img = Image.open(full_file_name)  # 读图
                            exif_dict = piexif.load(img.info['exif'])
                            # 修改exif数据
                            if 'photoTakenTime' in exifJson.keys():
                                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = datetime.fromtimestamp(int(
                                    exifJson['photoTakenTime']['timestamp'])).strftime("%Y:%m:%d %H:%M:%S").encode('utf-8')
                            if 'creationTime' in exifJson.keys():
                                exif_dict['0th'][piexif.ImageIFD.DateTime] = datetime.fromtimestamp(int(exifJson['creationTime']['timestamp'])).strftime(
                                    "%Y:%m:%d %H:%M:%S").encode('utf-8')
                            if 'photoLastModifiedTime' in exifJson.keys():
                                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = datetime.fromtimestamp(int(exifJson['creationTime']['timestamp'])).strftime(
                                    "%Y:%m:%d %H:%M:%S").encode('utf-8')
                            if 'geoDataExif' in exifJson.keys():
                                exif_dict['GPS'][piexif.GPSIFD.GPSLatitude] = self.format_latlng(
                                    exifJson['geoDataExif']['latitude'])
                                exif_dict['GPS'][piexif.GPSIFD.GPSLongitude] = self.format_latlng(
                                    exifJson['geoDataExif']['longitude'])
                            # exif_dict['GPS'][piexif.GPSIFD.GPSLongitudeRef] = 'W'
                            # exif_dict['GPS'][piexif.GPSIFD.GPSLatitudeRef] = 'N'
                            exif_bytes = piexif.dump(exif_dict)
                            img.save(full_file_name, None, exif=exif_bytes)
                            # 修改文件时间（可选）
                            # photoTakenTime = time.strftime("%Y%m%d%H%M.%S", time.localtime(int(exifJson['photoTakenTime']['timestamp'])))
                            # os.system('touch -t "{}" "{}"'.format(photoTakenTime, full_file_name))
                            # os.system('touch -mt "{}" "{}"'.format(photoTakenTime, full_file_name))

                            # print(type(exif_dict), exif_dict)
                            # for ifd in ("0th", "Exif", "GPS", "1st"):
                            #     print(ifd)
                            #     for tag in exif_dict[ifd]:
                            #         print(piexif.TAGS[ifd][tag], exif_dict[ifd][tag])
                        except UnidentifiedImageError:
                            print("图片读取失败：" + full_file_name)
                            continue
                        except KeyError:
                            print("图片没有exif数据" + full_file_name)
                            continue
                            # exif_dict = {'0th':{},'Exif': {},'GPS': {}}
                    else:  # 若该图片没有对应json
                        pass


    def dealSortByDate(self):
        """根据日期分类（原基础上复制）
        """
        g = os.walk(scanDir)
        for path, _, file_list in g:
            for file_name in tqdm(file_list, desc="dealSortByDate"):
                full_file_name = os.path.join(path, file_name)
                ext_name = os.path.splitext(file_name)[-1]
                if ext_name.lower() in ['.jpg', '.jpeg', '.png']:

                    if os.path.exists(os.path.join(self.jsonDir, file_name + '.json')):
                        exifJson = self.readJson(os.path.join(
                            self.jsonDir, file_name + '.json'))
                        try:
                            takenDate = datetime.fromtimestamp(
                                int(exifJson['photoTakenTime']['timestamp']))
                            takenYear = str(takenDate.year)
                            takenMonth = str(takenDate.month)

                            targetPath = os.path.join(
                                outPutDir, takenYear, takenMonth)
                            self.copy_to_target(
                                file_name=file_name, file_source_path=full_file_name, file_target_path=targetPath)
                        except Exception as e:
                            print(e)
                            targetPath = os.path.join(outPutDir, 'failedPic')
                            self.copy_to_target(
                                file_name=file_name, file_source_path=full_file_name, file_target_path=targetPath)

                    else:  # 若该图片没有对应json
                        try:
                            img = Image.open(full_file_name)  # 读图
                            exif_dict = piexif.load(img.info['exif'])
                            # 修改exif数据
                            try:
                                exif_str = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal].decode(
                                    'utf-8')
                                dt = datetime.strptime(
                                    exif_str, "%Y:%m:%d %H:%M:%S")
                                dtYear = str(dt.year)
                                dtMonth = str(dt.month)
                                targetPath = os.path.join(
                                    outPutDir, dtYear, dtMonth)
                                self.copy_to_target(
                                    file_name=file_name, file_source_path=full_file_name, file_target_path=targetPath)

                            except:
                                exif_str = exif_dict['0th'][piexif.ImageIFD.DateTime]
                                dt = datetime.strptime(
                                    exif_str, "%Y:%m:%d %H:%M:%S")
                                dtYear = str(dt.year)
                                dtMonth = str(dt.month)
                                targetPath = os.path.join(
                                    outPutDir, dtYear, dtMonth)
                                self.copy_to_target(
                                    file_name=file_name, file_source_path=full_file_name, file_target_path=targetPath)

                        except Exception as e:
                            print(e)
                            targetPath = os.path.join(outPutDir, 'failedPic')
                            self.copy_to_target(
                                file_name=file_name, file_source_path=full_file_name, file_target_path=targetPath)


    def copy_to_target(self, file_name: str, file_source_path: str, file_target_path: str):
        """复制到目标路径

        Args:
            file_name (str): 文件名
            file_source_path (str): 文件原路径
            file_target_path (str): 文件目标路径
        """
        if not os.path.exists(file_target_path):
            os.makedirs(file_target_path)
        targetFullPath = os.path.join(file_target_path, file_name)
        shutil.copyfile(file_source_path, targetFullPath)


    def check(self):
        """检查目录
        """
        outPutDirName = 'DealGoogleOutput'
        outPutDir = os.path.join(self.scanDir, outPutDirName)
        if self.scanDir == r'/Users/XXX/Downloads/Takeout':
            print("\033[31mPlease modify scanDir\033[0m")
            print("\033[31m请修改scanDir变量你的归档解压文件夹路径\033[0m")
            sys.exit()
        if not os.path.exists(outPutDir):
            os.makedirs(outPutDir)
        else:
            print("\033[31m请先移除路径\033[0m" + " \033[31m" + scanDir +
                outPutDir + "\033[0m" + " \033[31m避免重复扫描\033[0m")
            sys.exit()
        return outPutDir

if __name__ == '__main__':
    scanDir = r'D:\download\Takeout'  # TODO 这里修改归档的解压目录
    

    DEAL = DealGooglePhotosArchive(scanDir=scanDir)

    # 根据对应功能自行使用以下函数
    DEAL.dealDuplicate()
    DEAL.dealClassify()
    DEAL.dealExif()
    DEAL.dealSortByDate()

    print('处理完成，文件输出在：' + outPutDir)
    # print('终于搞完了，Google Photos 辣鸡')
