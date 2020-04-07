# -*- coding: utf-8 -*-
"""
author: siberiawind
解决了一些异常情况：
1. ConnectionError 发送HTTPS请求超时
    HTTPSConnectionPool(host='www.vlive.tv', port=443): Read timed out.
2. FANSHIP+的视频 在获取json时会返回404状态码 152198
"""
import os
import json
import re
import requests
import time
from tqdm import tqdm
from bs4 import BeautifulSoup

requests.adapters.DEFAULT_RETRIES = 10

header = {
    'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
    'Connection': 'close'
}

country_enum = ['CN', 'TW', 'US', 'KR']
type_enum = ['cp', 'fan', 'auto']


def getLocalFileSize(file_path):
    '''
    获取目标文件的大小
    :param: p_src: 输入的文件路径
    :param: p_dst: 文件的大小
    '''
    try:
        lsize = os.stat(file_path).st_size
    except:
        lsize = 0
    return lsize


def getObjContent(url_path, offset):
    '''
    断点续传功能，每次只获取url_path上offset字节大小的文件
    '''
    webPage = None
    try:
        headers = {'Range': 'bytes=%d-' % offset}
        webPage = requests.get(url_path, stream=True,
                               headers=headers, timeout=120, verify=False)

        status_code = webPage.status_code
        if status_code in [200, 206]:
            webPage = webPage
        elif status_code == 416:
            print("%s 文件请求错误, status code: %s" % (url_path, status_code))
        else:
            print("%s status code: %s" % (status_code))
    except Exception as e:
        print("无法链接:%s, e:%s" % (url_path, e))
    finally:
        return webPage


def vliveDescParser(html_text):
    '''
    解析vlive的网页内容:
        日期
        视频标题
        video ID
        key ID
    '''
    pattern1 = re.compile(r'<meta name="description" content="(.*?)"')
    title = re.findall(pattern1, bytes.decode(html_text))
    print(title[0])

    format_time = time.strptime(title[0].split('-')[0], "%b %d, %Y ")  # 格式化日期
    ret_time = time.strftime("%y%m%d", format_time)

    pattern2 = re.compile(r'<title>V LIVE - (.*?)</title>')
    # video_name = title[0].split('-')[2].strip()
    video_name = re.findall(pattern2, bytes.decode(html_text))[0]

    pattern = re.compile(r'vlive.video.init\(".*?", ".*?", ".*?", ".*?", '
                         '".*?",\n\t\t\t"(.*?)",\n\t\t\t"(.*?)"\,')

    parse_ret = re.findall(pattern, bytes.decode(html_text))
    vid = parse_ret[0][0]
    keyid = parse_ret[0][1]
    return vid, keyid, ret_time, video_name


def getJsonUrl(vid, keyid):
    '''
    利用vid, keyid获取包含视频信息的json文件
    '''
    return r"https://apis.naver.com/rmcnmv/rmcnmv/vod/play/v2.0/" + vid + \
        r"?key=" \
        + keyid + \
        r"&pid=rmcPlayer_15859223832761801&sid=2024&ver=2.0&devt=" \
        r"html5_pc&doct=json&ptc=https&sptc=https&cpt=vtt&ctls=%7B%22" \
        r"visible%22%3A%7B%22fullscreen%22%3Atrue%2C%22logo%22%3Afalse" \
        r"%2C%22playbackRate%22%3Afalse%2C%22scrap%22%3Afalse%2C%22" \
        r"playCount%22%3Atrue%2C%22commentCount%22%3Atrue%2C%22title%22" \
        r"%3Atrue%2C%22writer%22%3Atrue%2C%22expand%22%3Atrue%2C%22" \
        r"subtitles%22%3Atrue%2C%22thumbnails%22%3Atrue%2C%22quality%22%3A" \
        r"true%2C%22setting%22%3Atrue%2C%22script%22%3Afalse%2C%22logo" \
        r"Dimmed%22%3Atrue%2C%22badge%22%3Atrue%2C%22seekingTime%22%3Atrue" \
        r"%2C%22muted%22%3Atrue%2C%22muteButton%22%3Afalse%2C%22viewer" \
        r"Notice%22%3Afalse%2C%22linkCount%22%3Afalse%2C%22createTime%22" \
        r"%3Afalse%2C%22thumbnail%22%3Atrue%7D%2C%22clicked%22%3A%7B%22" \
        r"expand%22%3Afalse%2C%22subtitles%22%3Afalse%7D%7D&pv=4.18.40&dr=" \
        r"2560x1440&cpl=ko_KR&lc=ko_KR&adi=%5B%7B%22adSystem%22%3A%22TPA" \
        r"%22%7D%5D&adu=dummy&videoId=" + vid + r"&cc=CN"


if __name__ == "__main__":
    # 读入要下载的vlive视频列表文件
    link_txt = "IDLink.txt"
    with open(link_txt, "r", encoding="utf-8") as f:
        vIDlist = f.read().split('\n')

    dst_dir = r'G:\workspace\vlive'
    target_video_suffix = '.mp4'
    target_sub_suffix = '.vtt'

    vID_idx = 0
    vID_num = len(vIDlist)
    # 对列表中的每个文件都进行遍历
    while(vID_idx < vID_num):
        try:
            curr_html = requests.get(vIDlist[vID_idx],
                                     headers=header, timeout=(3, 7))
            html_text = curr_html.content
            vid, keyid, ret_time, video_name = vliveDescParser(html_text)

            # Fanship视频页面加载时对应的vid和keyid解析为空，这里需要做异常处理，并跳过该视频
            if vid == "" or keyid == "":
                vID_idx += 1
                raise ValueError("Fanship video")

            # 若vid和keyid均不为空，则通过这两个值得到json文件
            url_path = getJsonUrl(vid, keyid)

            # 请求Json地址对应的页面内容
            json_res = requests.get(url_path)
            # 若请求被拒绝，很有可能是IP被暂时禁用了，这里做一个异常处理，返回本次循环的结尾sleep30秒
            if (json_res == 404):
                raise ValueError("Json file requested failed!")

            json_text = json.loads(json_res.text)

            # 获取Json文件中所有的MP4下载链接
            down_mp4_links = json_text['videos']['list']
            max_pixel = 0
            final_mp4_link = ""
            final_mp4_size = 0
            for mp4_idx in range(len(down_mp4_links)):
                curr_mp4_link = down_mp4_links[mp4_idx]
                curr_pixel = curr_mp4_link['encodingOption']['height']
                if(max_pixel <= curr_pixel):
                    max_pixel = curr_pixel
                    final_mp4_link = curr_mp4_link['source']
                    final_mp4_size = curr_mp4_link['size']

            print(final_mp4_link)
            print("current mp4 pixel size is: %dP" % max_pixel)
            print("file size: %.2f MB" % (final_mp4_size / 1024 / 1024))

            output_name = '['+ret_time+']['+video_name+']'
            while True:
                local_mp4_path = os.path.join(dst_dir,
                                              output_name+target_video_suffix)
                lsize = getLocalFileSize(local_mp4_path)
                if lsize == final_mp4_size:
                    break

                webPage = getObjContent(final_mp4_link, lsize)
                try:
                    file_obj = open(local_mp4_path, "ab+")
                except Exception as e:
                    print("打开文件:%s失败" % local_mp4_path)
                    break

                try:
                    for chunk in webPage.iter_content(chunk_size=64*1024):
                        if chunk:
                            file_obj.write(chunk)
                        else:
                            break
                except Exception as e:
                    time.sleep(5)

                file_obj.close()
                webPage.close()

            vID_idx += 1

            # 获取Json文件中所有的vtt字幕，因为可能视频没有字幕，所以需要做异常处理
            try:
                down_vtt_links = json_text['captions']['list']
                final_vtt_link = ""
                final_vtt_links = []
                for vtt_idx in range(len(down_vtt_links)):
                    curr_vtt_link = down_vtt_links[vtt_idx]
                    for lang_idx in range(len(country_enum)):
                        if country_enum[lang_idx] == curr_vtt_link['country']:
                            final_vtt_link = curr_vtt_link['source']
                            final_vtt_links.append(final_vtt_link)
                            print(final_vtt_link)
            except KeyError:
                print("no subtitle")

        except Exception as e:
            print("Exception: {}".format(e))
            time.sleep(30)
