# -*- coding: utf-8 -*-
import os
import requests
import re
import slackweb
import psycopg2
from psycopg2 import extras

from bs4 import BeautifulSoup
from requests_html import HTMLSession

DATABASE_URL = os.environ['DATABASE_URL']
SLACK_WEBHOOK_URL = os.environ['SLACK_WEBHOOK_URL']

HIDDEN_CATEGORY = 'マンガ'
result = []


def resub(text):
    return re.sub(r"[,.:;'\"\n]", "", text).strip()


def scraping_white_cross():
    r = requests.get('https://www.whitecross.co.jp/articles')
    soup = BeautifulSoup(r.text, 'html.parser')

    for news in soup.find(class_='main f_left').find_all(class_='unit_block_02'):
        category = resub(news.find(class_='label_contents').text)
        title = resub(news.find(class_='title').text)
        url = 'https://www.whitecross.co.jp' + news.find('a').get('href')
        writer = resub(news.find(class_='users').find(class_='wrap_sub').text)
        if category not in HIDDEN_CATEGORY:
            result.append((
                title,
                url,
                category,
                writer
            ))


def scraping_doctor_book():
    r = requests.get('https://academy.doctorbook.jp/contents')
    soup = BeautifulSoup(r.text, 'html.parser')

    for news in soup.find_all(class_='page_drvideo_list'):
        category = resub(news.find(class_='page_drvideo_episode').find('span').text)
        title = resub(news.find(class_='page_drvideo_episode').text)
        title = resub(title.removeprefix(category))
        url = 'https://academy.doctorbook.jp' + news.find('a').get('href')
        if news.find(class_='page_drvideo_dr') is None:
            writer = '-'
        else:
            writer = resub(news.find(class_='page_drvideo_dr').text)
        if category not in HIDDEN_CATEGORY:
            result.append((
                title,
                url,
                category,
                writer
            ))


def scraping_1d():
    session = HTMLSession()
    r = session.get('https://oned.jp/posts')
    r.html.render(timeout=20)

    for news in r.html.find('.scoped-post-list-item-inner'):
        category = 'ニュース'
        title = resub(news.find('.scoped-post-title')[0].text)
        url = news.find('.scoped-post-list-item-inner a')[0].attrs["href"]
        writer = resub(news.find('.scoped-post-author')[0].text)
        if HIDDEN_CATEGORY not in title:
            result.append((
                title,
                'https://oned.jp' + url,
                category,
                writer
            ))


def read_data():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as curs:
            curs.execute('SELECT title, url, category, writer FROM news')
            return curs.fetchall()


def add_data(insert_list):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as curs:
            extras.execute_values(
                curs,
                "INSERT INTO news(title, url, category, writer) VALUES %s", insert_list)


def list_up_new_data():
    new_data = []
    for tmp in result:
        if tmp not in last_result:
            new_data.append(tmp)
            last_result.append(tmp)
    return new_data


def send_to_slack(text):
    slack = slackweb.Slack(url=SLACK_WEBHOOK_URL)
    slack.notify(text=text)


def send_to_slack_diff_list(diff_list):
    text = ''
    for tmp in diff_list:
        if len(tmp[3]) == '-':
            text += '[' + tmp[2] + ']' + tmp[0] + '\n' + tmp[1] + '\n'
        else:
            text += '[' + tmp[2] + ']' + tmp[0] + '(' + tmp[3] + ')\n' + tmp[1] + '\n'
    send_to_slack(text)


print('scraping white cross')
scraping_white_cross()

print('scraping id')
scraping_1d()

print('scraping doctor book')
scraping_doctor_book()

print('read last result csv')
last_result = read_data()

print('check add news')
add_news = list_up_new_data()

if len(add_news) > 0:
    print('add news -> ' + str(len(add_news)))
    print('send slack')
    send_to_slack_diff_list(add_news)

    print('add data')
    add_data(add_news)

else:
    print('no news')
