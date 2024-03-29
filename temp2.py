# -*- coding: utf-8 -*-
"""
Created on Mon May 27 19:34:46 2019

@author: dell
"""

import re
import sqlite3
import pymysql
import time
import threading
import sys
from redis import StrictRedis
import requests
from spider2 import Spider

class Film:
    #初始化连接
    def __init__(self):
        self.redis=StrictRedis(host='192.168.2.119',port=6379,decode_responses=True)
        #支持多线程操作
        self.conn=sqlite3.connect('film.sqlite3',check__name_thread=False)
        self.cursor = self.conn.cursor()
        #创建锁
        self.cursor_lock=threading.Lock()
        self.test_db()
        self.iter_get_all_page_url=self.get_all_show_page_url_yield()
    #创建表
    def test_db(self):
        create_sql='''CREATE TABLE IF NOT EXISTS film_info(
                    id INT PRIMARY KEY auto_increment,
                    name VARCHAR(120),
                    url VARCHAR(255) UNIQUE,
                    update_time VARCHAR(255),
                    type VARCHAR(255),
                    status TEXT NULL
                    )'''
        ##获取锁
        self.cursor_lock.acquire()
        
        self.cursor.execute(create_sql)
        self.conn.commit()
        
        ##释放锁,一定要释放锁,否则会成死线程
        self.cursor_lock.release()
        
    ##处理导演字段   
    def split_info(self,info_str):
        ##导演
        if '/' in info_str:
            info_str=info_str.split('/')
        elif ',' in info_str:
            info_str=info_str.split(',')
        elif ' ' in info_str:
            info_str=info_str.split(' ')
        else:
            info_str=[info_str]
        return [i.strip() for i in info_str if i != '']
    
    ##返回电影详情字段(字典)
    def get_film_info(self,url,encoding=None):
        regex=dict(
                intro='<div class="vodplayinfo">(.*?)</div>',
                name='<h2>(.*?)</h2>\s+?<span>(.*?)</span>\s+?<label>(.*?)</label>',
                info='\
 <li>别名：<span>(.*?)</span></li>\s+?\
<li>导演：<span>(.*?)</span></li>\s+?\
<li>主演：<span>(.*?)</span></li>\s+?\
<li>类型：<span>(.*?)</span></li>\s+?\
<li class="sm">地区：<span>(.*?)</span></li>\s+?\
<li class="sm">语言：<span>(.*?)</span></li>\s+?\
<li class="sm">上映：<span>(.*?)</span></li>\s+?\
<li class="sm">片长：<span>(.*?)</span></li>\s+?\
<li class="sm">更新：<span>(.*?)</span></li>\s+?\
<li class="sm">总播放量：<span><em id="hits">.*?</script></span></li>\s+?\
<li class="sm">今日播放量：<span>(.*?)</span></li>\s+?\
<li class="sm">总评分数：<span>(.*?)</span></li>\s+?\
<li class="sm">评分次数：<span>(.*?)</span></li>',
                show_list='checked="" />(.*?)</li>'
                )
      
        info = Spider().get_info(url, encoding = encoding, **regex)
        
        director = self.split_info(info['info'][0][1])
            
        actor = self.split_info(info['info'][0][2])
        
        types = self.split_info(info['info'][0][3])
        
        area = self.split_info(info['info'][0][4])
        
        language = self.split_info(info['info'][0][5])
        
        m3u8_list = [url  for url in info['show_list'] if url.endswith('.m3u8')]
        
        yun_list = [url  for url in info['show_list'] if not url.endswith('.m3u8')]
        
        film_info=dict(
                
                name=info['name'][0][0],
                
                name_info=info['name'][0][1],
                
                grade=info['name'][0][2],
                ##别名
                author_name=info['info'][0],
                director=director,
                actor=actor,
                types=types,
                area=area,
                language=language,
                show_time = info['info'][0][6],
                
                lens = info['info'][0][7],
                
                up_date = info['info'][0][8],
                
                day_plays = info['info'][0][9],
                
                total_score =info['info'][0][10],
                
                total_score_number = info['info'][0][11],
                
                m3u8_list = m3u8_list,
                
                yun_list = yun_list,
               
                )
        
        return film_info
    
    
    def film_search(self,keyword, encoding = None):
        post_url = 'https://www.subo8988.com/index.php?m=vod-search'
        
        data = {
                'wd': keyword,
                'submit': 'search',
                }
        regex = dict(
                    info = '<li><span class="tt"></span><span class="xing_vb4"><a href="(.*?)" target="_blank">(.*?)</a></span> <span class="xing_vb5">(.*?)</span> <span class="xing_vb6">(.*?)</span></li>'
                    )
        
        info = Spider().post_info(post_url, data, encoding, **regex)
        print(info)
        join_url='https://www.subo8988.com'
        info=[{'url':join_url+url,'name':name,'types':types,'update_time':update_time} for url, name, types, update_time in info['info']]
        return {'search_list':info, 'search_word':keyword, 'host': join_url}
    
    '''
    动作片  5  喜剧片 6 爱情片 7 科幻片 8  恐怖片 9  剧情片 10 战争片 11 理论片 16
    国产剧 12 香港剧 13 日本剧 14 欧美剧  15  台湾剧 17  韩国剧  18  海外 19
    综艺  3  动漫 4  音乐MTV 20
    '''
    ##获取全部url
    def get_all_show_page_url_yield(self):
        url='https://www.subo8988.com/?m=vod-index-pg-{}.html'
        for i in range(1,485):
            yield url.format(i)
    
    #网站的所有url和相关字段
    def get_page_film(self,url):
        regex = dict(
                    info = '<li><span class="tt"></span><span class="xing_vb4"><a href="(.*?)" target="_blank">(.*?)</a></span> <span class="xing_vb5">(.*?)</span> <span class="xing_vb[67]">(.*?)</span></li>'
                    )
        info=Spider().get_info(url,encoding='utf-8',**regex)['info']
        info=[dict(url=i[0],name=i[1].split('&nbsp;')[0],types=i[2],update_time=i[3]) for i in info]
        return {'film_list':info}

    
    def save_all_film_info(self):
        ##添加字段
        insert_sql='''insert into film_info(name,url,update_time,type) values(?,?,?,?)'''

        que=self.get_all_show_page_url_yield()
        start=time.time()
        for i in que[:10]:
            info=self.get_page_film(i)['film_list']
#            for i in info:
#                cursor.execute(insert_sql,[i['name'],i['url'],i['update_time'],i['types']])
#                conn.commit()
            insert_list=[(i['name'],i['url'],i['update_time'],i['types']) for i in info]
            cursor.executemany(insert_sql,insert_list)
            conn.commit()
        print('耗时',time.time()-start)
    def work(self):
        
        insert_sql='''insert into film_info(name,url,update_time,type) values(%s,%s,%s,%s)'''
        
        config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'passwd': '',
            'db':'aa',
            'charset':'utf8'
        }
        conn = pymysql.connect(**config)
        cursor = conn.cursor()
        
        while True:
         
            show_page_url = self.queue.pop()
            
            try:
            
                info = self.get_page_film(show_page_url)['film_list']
                
            except requests.exceptions.ConnectionError:
                
                self.redis.set(show_page_url, str(sys.exc_info()))
                
                print('出错啦', show_page_url)
                
            else:
                
      
                insert_list = [(i['name'], i['url'], i['update_time'], i['types']) for i in info]
                    
                cursor.executemany(insert_sql, insert_list)
                
                conn.commit()
                
                print(show_page_url)
            
    def my_thread(self):
        
        self.get_all_show_page_url()
        
        for i in range(5):
        
            t = threading.Thread(target = self.work)#, args = (), kwargs = {})
            
            t.start()
        
        
if __name__ == "__main__":
    x=Film()
    x.save_all_film_info()
#    url='https://www.subo8988.com/?m=vod-index-pg-5.html' 
#    info=x.get_page_film(url)
    
            
import sys
import traceback

try:
    raise KeyError
except:
    print(sys.exc_info())
    traceback.print_tb(sys.exc_info()[2])
            
            
import unittest

class TestStringMethods(unittest.TestCase):

    def test_upper(self):
        self.assertEqual('foo'.upper(), 'FOO')

    def test_isupper(self):
        self.assertTrue('FOO'.isupper())
        self.assertFalse('Foo'.isupper())

    def test_split(self):
        s = 'hello world'
        self.assertEqual(s.split(), ['hello', 'world'])
        # check that s.split fails when the separator is not a string
        with self.assertRaises(TypeError):
            s.split(2)

if __name__ == '__main__':
    unittest.main()         
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            