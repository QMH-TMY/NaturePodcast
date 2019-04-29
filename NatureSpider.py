#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# 26.Apr 2019 
# Shieber in UESTC 
# QMH_XB_FLTMY@yahoo.com
# 

import re
import os
import sys
import logging
import time
from bs4 import BeautifulSoup
from tqdm import tqdm
from requests import get
from contextlib import closing
from urllib.parse import urljoin
from multiprocessing import Pool
logging.basicConfig(level=logging.DEBUG,format='%(asctime)s-%(message)s')

class Spider():
    def __init__(self,storedir='Nature'):
        self.headers    = {'User-Agent':'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:66.0) Gecko/20100101 Firefox/66.0', 'Connection':'close'}
        self.root_url1  = "https://www.nature.com"
        self.root_url2  = "https://www.nature.com/nature/articles?type=nature-podcast"
        self.podprefix  = 'Nature-' 
        self.storedir   = storedir 
        self.years      = set() 
        self.year_urls  = set() 

    #********************1.初始化*******************************
    def get_year_urls(self):
        '''获取对应年播客列表的url并准备好相应的目录以备存储下载内容'''
        html_res = get(self.root_url2,headers=self.headers)
        if 200 == html_res.status_code:
            html_res.encoding='utf-8'
            res = self._set_year_urls(html_res.text) 

            if res:
                for year in self.years:
                    store_dir = ''.join([self.storedir,year])
                    if not os.path.exists(store_dir):
                        os.makedirs(store_dir) #创建对应年文件夹
            else:
                sys.exit(-1)
        else:
            sys.exit(-1)
    
    def _set_year_urls(self,html_cnt):
        '''提取各个年度的url'''
        root_url = "https://www.nature.com/nature/articles"
        soup     = BeautifulSoup(html_cnt,'html.parser') 
        patn     = re.compile(r'\?type=nature-podcast')
        links    = soup.find_all('a',href=patn)
        try:
            for link in links:
                self.years.add(link.getText()[:4])
                year_url = urljoin(root_url,link['href'])
                self.year_urls.add(year_url)
        except Exception as err:
            print(err)
            return False
        return True

    #********************2.音频和脚本文件下载函数***************
    def _download_podcast(self,radio_url,radio_name):
        with closing(get(radio_url,stream=True,headers=self.headers)) as res:
            size = 1024*20
            content_size = int(res.headers['content-length'])

            if os.path.exists(radio_name) and os.path.getsize(radio_name) >= content_size:
                return True 

            info = ''.join(['downloading from Nature... ',os.path.basename(radio_name)])
            with open(radio_name,'wb') as rObj:
                for chunk in tqdm(res.iter_content(chunk_size=size),ascii=True,desc=info):
                    rObj.write(chunk)

    def _download_transcript(self,soup,script_name):
        content  = soup.find('div',class_="article__transcript") 
        if content == None:
            return None

        title    = content.find('h3').getText() 
        subtitle = content.find('h4').getText() 
        with open(script_name,'w') as fObj:
            fObj.write(''.join([title,': \n']))
            fObj.write(''.join([subtitle,'\n\n\n']))

            n = 0
            text  = []
            paras = content.find_all('p')
            for para in paras:
                n += 1
                tx = para.getText().replace('Interviewer: ','').replace('Interviewee: ','') 
                if n %2 == 0:
                    text.append(''.join([tx,'\n\n']))
                else:
                    text.append(''.join([tx,': \n']))
                if len(text) == 20:
                    fObj.write(''.join(text))
                    text = []

            if text != []:
                fObj.write(''.join(text))

    #********************3.播客文件名和音频链接提取器***********
    def _get_radio_name_and_url(self,year,soup):
        '''抽取信息以设置音频和文本的名字'''
        patn        = re.compile(r'/magazine-assets/(\S+)/(\S+)\.mpga')
        link        = soup.find('a',href=patn) 

        timestr     = soup.find('time',attrs={'itemprop':'datePublished'}) 
        timetxt     = timestr.getText().split()
        timename    = '-'.join(timetxt)

        flprefix    = ''.join([self.storedir, year, '/'])
        basename    = ''.join([self.podprefix,timename])

        radio_name  = ''.join([flprefix, basename, '.mp3'])
        script_name = ''.join([flprefix, basename, '.txt'])

        radio_url   = ''.join([self.root_url1,link['href']]) 

        return radio_name,script_name,radio_url

    #********************4.分布式播客下载处理器*****************
    def _func(self,url,year):
        time.sleep(3) #爬取速度缓和
        html_res = get(url,headers=self.headers)
        if 200 == html_res.status_code:
            html_res.encoding = 'utf-8'
            soup  = BeautifulSoup(html_res.text,'html.parser') 
            radio_name,script_name,radio_url = self._get_radio_name_and_url(year,soup)

            if not os.path.exists(script_name): 
                self._download_transcript(soup,script_name)

            if not os.path.exists(radio_name): 
                self._download_podcast(radio_url,radio_name)

    def _download_multi(self,year,urls):
        '''分布式爬虫'''
        if urls == []:
            return None

        pool = Pool(5)
        for url in urls:
            pool.apply_async(self._func,(url,year))

        pool.close()
        pool.join()

    #********************5.下一页链接和当前页播客链接***********
    def _getpd_urls_nexl(self,url):
        '''获取当年的博客目录和下一页链接'''
        next_url = None 
        podcast_urls = [] 

        html_res = get(url.replace("&amp;","&"),headers=self.headers)
        if 200 == html_res.status_code:
            html_res.encoding='utf-8'
            soup  = BeautifulSoup(html_res.text,'html.parser') 

            #1.提取下一页链接
            link  = soup.find('li',attrs={'data-page':'next'}) 
            if link != None:
                patn=re.compile(r'/nature/articles\?searchType=(.*?)year(.*?)page=\d')
                match = patn.search(str(link))
                try:
                    next_url = urljoin(self.root_url1,match.group(0))
                except:
                    next_url = None 
            #2.提取本页播客项
            patn  = re.compile(r'/articles/(\w+)')
            links = soup.find_all('a',href=patn)
            if links != None: 
                podcast_urls=[urljoin(self.root_url1,link['href']) for link in links] 

        return next_url, podcast_urls

    #********************6.下载启动器***************************
    def main_control(self):
        ''''下载控制器'''
        for year_url in self.year_urls:
            year = year_url[-4:]
            next_url,podcast_urls = self._getpd_urls_nexl(year_url)
            self._download_multi(year,podcast_urls)

            while next_url != None:
                next_url,podcast_urls = self._getpd_urls_nexl(next_url)
                self._download_multi(year,podcast_urls)

            os.system('sh trans2pdf.sh %s'%(''.join([self.storedir,year,'/'])))

if __name__ == "__main__":
    logging.disable(logging.CRITICAL)                  #调试已关闭
    start = time.time()

    spider = Spider()
    try:
        spider.get_year_urls()
        spider.main_control()
    except Exception as err:
        print(err)
    finally:
        end = time.time()
        minute = (end - start)/60
        print("Download done in %.2f minute(s)."%(minute))
        #print("下载完成，用时%.2f分钟."%(minute)) 

