#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
#    Author: Shieber
#    Date: 2019.04.30
#
#                             APACHE LICENSE
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
#                            Function Description
#    download podcasts from Nature.com website.   
#
#    Copyright 2019 
#    All Rights Reserved!

import re
import os
import sys
import logging
import time
import requests
import os.path as path
from bs4 import BeautifulSoup
from tqdm import tqdm
from requests import get
from contextlib import closing
from urllib.parse import urljoin
from multiprocessing import Pool

logging.basicConfig(level=logging.DEBUG,format='%(asctime)s-%(message)s')

class Spider():
    def __init__(self,max_job=5,storedir='Nature'):
        self.headers    = {
                            'User-Agent':'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:66.0) \
                             Gecko/20100101 Firefox/66.0', 
                            'Connection':'close'}
        self.website_url= "https://www.nature.com"
        self.podcst_url = "https://www.nature.com/nature/articles?type=nature-podcast"
        self.showstr    = 'downloading from Nature... '
        self.podprefix  = 'Nature-' 
        self.max_job    = max_job
        self.storedir   = storedir 
        self.years      = set() 
        self.year_urls  = set() 
        self.downloaded = 0

    #********************1.初始化*******************************
    def _mkdir_for_year(self):
        for year in self.years:
            store_dir = ''.join([self.storedir,year])
            if not path.exists(store_dir):
                os.makedirs(store_dir)         #创建对应年文件夹

    def get_year_urls(self):
        '''获取对应年播客列表的url并准备好相应的目录以备存储下载内容'''
        soup = self._get_url_content(self.podcst_url)
        if soup:
            res = self._get_urls(soup) 
            if res:
                self._mkdir_for_year()
            else:
                sys.exit(-1)
        else:
            sys.exit(-1)
    
    def _get_urls(self, soup):
        '''提取各个年度的url'''
        root_url = "https://www.nature.com/nature/articles"
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
    def _download_podcast(self,url,fl_name):
        s = requests.session()
        s.keep_alive = False
        size = 1024*20
        with closing(s.get(url,stream=True,headers=self.headers)) as res:
            content_size = int(res.headers['content-length'])
            if path.exists(fl_name) and path.getsize(fl_name) >= content_size:
                return True 

            info = ''.join([self.showstr, path.basename(fl_name)])
            with open(fl_name,'wb') as rObj:
                for ck in tqdm(res.iter_content(chunk_size=size),ascii=True,desc=info):
                    rObj.write(ck)

            self.downloaded += 1

    def _download_transcript(self,soup,script_name):
        content  = soup.find('div',class_="article__transcript") 
        if not content:
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

            if text:
                fObj.write(''.join(text))

    #********************3.播客文件名和音频链接提取器***********
    def _get_radio_name_and_url(self,year,soup):
        '''抽取信息以设置音频和文本的名字'''
        patn        = re.compile(r'/magazine-assets/(\S+)/(\S+)\.mpga')
        link        = soup.find('a',href=patn) 

        timestr     = soup.find('time',attrs={'itemprop':'datePublished'}) 
        timestr     = timestr.getText().split()
        timemid     = '-'.join(timestr)

        dirprefix   = ''.join([self.storedir, year, '/'])
        midname     = ''.join([self.podprefix,timemid])

        radio_name  = ''.join([dirprefix, midname, '.mp3'])
        script_name = ''.join([dirprefix, midname, '.txt'])

        radio_url   = ''.join([self.website_url,link['href']]) 

        return radio_name,script_name,radio_url

    #********************4.分布式播客下载处理器*****************
    def _func(self,url,year):
        soup = self._get_url_content(url)
        if soup:
            radio_name,script_name,radio_url = self._get_radio_name_and_url(year,soup)

            if not path.exists(script_name): 
                self._download_transcript(soup,script_name)
            if not path.exists(radio_name): 
                self._download_podcast(radio_url,radio_name)

    def _download_multi(self,year,urls):
        '''分布式爬虫'''
        if not urls:
            return None

        pool = Pool(self.max_job)
        for url in urls:
            pool.apply_async(self._func,(url,year))

        pool.close()
        pool.join()

        time.sleep(5)                          #爬取速度缓和

    def _download_single(self,year,urls):
        if not urls:
            return None

        for url in urls:
            self._func(url,year)

    #********************5.下一页链接和当前页播客链接***********
    def _getpd_urls_nexl(self,url):
        '''获取当年的博客目录和下一页链接'''
        next_url = None 
        podcast_urls = [] 

        soup = self._get_url_content(url)
        if soup:
            #1.提取下一页链接
            link  = soup.find('li',attrs={'data-page':'next'}) 
            if link:
                patn=re.compile(r'/nature/articles\?searchType=(.*?)year(.*?)page=\d')
                match = patn.search(str(link))
                try:
                    next_url = urljoin(self.website_url,match.group(0))
                except:
                    next_url = None 

            #2.提取本页播客项
            patn  = re.compile(r'/articles/(\w+)')
            links = soup.find_all('a',href=patn)
            if links: 
                podcast_urls=[urljoin(self.website_url,lk['href']) for lk in links] 

        return next_url, podcast_urls

    #********************6.下载启动器***************************
    def _get_url_content(self, url):
        '''网页下载函数'''
        s = requests.session()
        s.keep_alive = False
        html_res = s.get(url,headers=self.headers)
        if 200 == html_res.status_code:
            html_res.encoding='utf-8'
            soup = BeautifulSoup(html_res.text,'html.parser') 
            return soup
        else:
            return None

    def main_control(self):
        ''''下载控制器'''
        self.get_year_urls()                           #初始化网页信息
        for year_url in self.year_urls:
            year = year_url[-4:]
            if year != year_urls[0][-4:]:  # 最新一年
                continue 
            next_url,podcast_urls = self._getpd_urls_nexl(year_url)
            self._download_multi(year,podcast_urls)
            #self._download_single(year,podcast_urls) # 
        
            while next_url:
                next_url,podcast_urls = self._getpd_urls_nexl(next_url)
                self._download_multi(year,podcast_urls)
                #self._download_single(year,podcast_urls) #

            os.system('sh trans2pdf.sh %s'%(''.join([self.storedir,year,'/'])))

if __name__ == "__main__":
    logging.disable(logging.CRITICAL)                  #调试已关闭
    requests.adapters.DEFAULT_RETRIES = 5

    start = time.time()
    spider = Spider()
    try:
        spider.main_control()
    except Exception as err:
        print(err)
    finally:
        end = time.time()
        minute = (end - start)/60
        print("Download %d podcast(s) done in %.2f minute(s)."%(spider.downloaded,minute))
