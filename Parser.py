import csv
import requests
from lxml import html
import telebot
from telebot import types
import pandas as pd
import json
import time
from realty import check_database
from selectolax.parser import HTMLParser
from urllib.parse import unquote
from datetime import datetime
from openpyxl import load_workbook


telegram_key = ''
bot = telebot.TeleBot(telegram_key)

cars_company_dict = ('bmw', 'audi', 'ford', 'land_rover', 'lexus', 'mercedes', 'porsche', 'volkswagen', 'volvo')
car_bodytype_dict = ('body-coupe/', 'body-allroad_5_doors/', 'body-sedan')

car_year_start_i = 2016
car_year_start = f'?year_from={car_year_start_i}'
car_year_end_i = 2020
car_year_end = f'&year_to={car_year_end_i}'


def get_json_data_avito(url):
    data = {}
    response = requests.get(url=url)
    html = response.text

    tree = HTMLParser(html)
    scripts = tree.css('script')
    for script in scripts:
        if 'window.__initialData__' in script.text():
            jsontext = script.text().split(';')[0].split('=')[-1].strip()
            jsontext = unquote(jsontext)
            jsontext = jsontext[1:-1]

            data = json.loads(jsontext)

    return data


def get_offer_avito(item):
    offer = {}
    SITE = 'https://www.avito.ru'
    offer['url'] = SITE + item['urlPath']
    offer['offer_id'] = item['id']
    offer['price'] = item['priceDetailed']['value']
    offer['subway'] = item['geo']['geoReferences'][0]['content']
    title = item['title'].split(',')
    area = float(title[1].replace('\xa0м²', '').replace(',', '.'))
    offer['area'] = area
    timestamp = datetime.fromtimestamp(item['sortTimeStamp']/1000)
    timestamp = datetime.strftime(timestamp, '%Y-%m-%d %H:%M:%S')
    offer['date'] = timestamp

    return offer


def get_offers_avito(data):
    offers = []
    for key in data:
        if 'single-page' in key:
            items = data[key]['data']['catalog']['items']
            for item in items:
                if item.get('id'):
                    offer = get_offer_avito(item)
                    check_database(offer)


def avito_realty():
    url = 'https://www.avito.ru/moskva/kvartiry/sdam/na_dlitelnyy_srok-ASgBAgICAkSSA8gQ8AeQUg?f=ASgBAQECAkSSA8gQ8AeQUgFA0vsONP7q4wKG6~MCiOvjAgNF6AcVeyJmcm9tIjo0OCwidG8iOm51bGx9ji4UeyJmcm9tIjozLCJ0byI6bnVsbH3GmgwZeyJmcm9tIjo2MDAwMCwidG8iOjgwMDAwfQ&s=104'
    data = get_json_data_avito(url)
    get_offers_avito(data)


def get_json_ya():
    headers = {
    }
    params = {
        'priceMin': '60000',
        'priceMax': '80000',
        'areaMin': '48',
        'floorMin': '3',
        'hasAircondition': 'YES',
        'hasDishwasher': 'YES',
        'sort': 'DATE_DESC',
        'rgid': '587795',
        'type': 'RENT',
        'category': 'APARTMENT',
        '_pageType': 'search',
        '_providers': [
            'seo',
            'queryId',
            'forms',
            'filters',
            'filtersParams',
            'mapsPromo',
            'newbuildingPromo',
            'refinements',
            'search',
            'react-search-data',
            'searchHistoryParams',
            'searchParams',
            'searchPresets',
            'showSurveyBanner',
            'seo-data-offers-count',
            'related-newbuildings',
            'breadcrumbs',
            'ads',
            'cache-footer-links',
            'site-special-projects',
            'offers-stats',
        ],
        'crc': '',
    }
    response = requests.get('https://realty.yandex.ru/gate/react-page/get/', params=params, headers=headers)
    data = response.json()

    return data


def get_offer_ya(item):
    offer = {}
    offer['url'] = item['shareUrl']
    offer['offer_id'] = item['offerId']
    offer['price'] = item['price']['value']
    offer['subway'] = item['location']['metro']['name']
    offer['area'] = item['area']['value']
    offer_date = ''
    offer_date = item['creationDate'].replace('T', ' ').replace('Z', '')
    offer['date'] = offer_date

    return offer


def get_offers_ya(data):
    for item in data['response']['search']['offers']['entities']:
        offer = get_offer_ya(item)
        check_database(offer)


def yandex_realty():
    data = get_json_ya()
    get_offers_ya(data)


def HeadHunter(job):
    def get_page(page=0):

        params = {
            'text': f'Name:{job}',
            'area': 1,
            'page': page,
            'per_page': 100
        }

        req = requests.get('https://api.hh.ru/vacancies', params)
        data = req.content.decode()
        req.close()
        return data

    js_objs = []

    for page in range(0, 2):
        js_obj = json.loads(get_page(page))
        js_objs.extend(js_obj['items'])
        if js_obj['pages'] - page <= 1:
            break
        time.sleep(0.25)

    df = pd.DataFrame(js_objs)
    second_df = df.drop(columns=['id', 'premium', 'department', 'has_test', 'response_letter_required', 'area', 'type', 'address',\
                     'response_url', 'sort_point_distance', 'published_at', 'created_at', 'archived',\
                     'apply_alternate_url', 'insider_interview', 'url', 'adv_response_url', 'relations', 'snippet',\
                     'contacts', 'schedule', 'working_days', 'working_time_intervals', 'working_time_modes',\
                     'accept_temporary'], axis=1)

    excel_file = load_workbook('hh_data.xlsx')
    excel_sheet = excel_file['Sheet1']

    for i in range(len(second_df)):
        excel_sheet[f'A{1 + i}'] = second_df.iat[i, 0]  # name
        excel_sheet[f'B{1 + i}'] = second_df.iat[i, 2]  # link
        excel_sheet[f'C{1 + i}'] = second_df.iat[i, 3]['name']  # link

    excel_file.save('hh_data.xlsx')

    return df


def get_cars_info(i, ii):
    cars_company_number = cars_company_dict[i]
    cars_bodytype_number = car_bodytype_dict[ii]
    r = requests.get(
        f'https://auto.ru/moskva/cars/{cars_company_number}/all/{cars_bodytype_number}{car_year_start}{car_year_end}')
    tree = html.fromstring(r.content)

    titles_xpath = tree.xpath('//a[@class ="Link ListingItemTitle__link"]//text()')
    link_xpath = tree.xpath('//a[@class ="Link ListingItemTitle__link"]//@href')
    prices_xpath = [
        price.replace(u'\xa0', '').replace(u'₽', '').replace(u'от ', '').replace(u'без скидок ', '')
        for price in tree.xpath(
            '//div[@class ="ListingItemPrice__content"]//text()')
    ]
    years_xpath = tree.xpath('//div[@class ="ListingItem__year"]//text()')
    params_xpath = [
                       param.replace(u'\u2009', '').replace(u'\xa0', '') for param in tree.xpath(
            '//div[@class ="ListingItemTechSummaryDesktop__cell"][1]//text()')
                   ][::2]
    milage_xpath = [
        milage.replace(u'\xa0', '').replace(u'км', '') for milage in tree.xpath(
            '//div[@class ="ListingItem__kmAge"]//text()')
    ]

    with open('auto.csv', mode='w') as file:
        writer = csv.writer(file, delimiter=';')
        Zagolovok = ('Название модели', 'Характеристеки машины', 'Год', 'Пробег', 'Цена', 'Ссылка на объявление')
        writer.writerow(Zagolovok)
        for index in range(len(titles_xpath)):
            writer.writerow([titles_xpath[index], params_xpath[index], years_xpath[index], milage_xpath[index], prices_xpath[index], link_xpath[index]])

    return link_xpath


def get_data_price():
    data = pd.read_csv('auto.csv', sep=";")
    data_price = data.groupby('Год')['Цена'].mean().round(2).reset_index()
    data_price['Цена'] = data_price.apply(lambda x: "{:,}".format(x['Цена']), axis=1)

    return data_price


def get_data_milage():
    data = pd.read_csv('auto.csv', sep=";")
    data_milage = data.groupby('Год')['Пробег'].mean().round(2).reset_index()
    data_milage['Пробег'] = data_milage.apply(lambda x: "{:,}".format(x['Пробег']), axis=1)

    return data_milage


def keyboard(where_call):
    kb = types.InlineKeyboardMarkup()
    if where_call == 'start':
        kb_1_1 = types.InlineKeyboardButton(text='auto.ru', callback_data='auto.ru')
        kb_1_2 = types.InlineKeyboardButton(text='hh.ru', callback_data='hh.ru')
        kb_1_3 = types.InlineKeyboardButton(text='Аренда Янд', callback_data='yandex_realty_')
        kb_1_4 = types.InlineKeyboardButton(text='Аренда Авито', callback_data='avito_realty_')

        kb.add(kb_1_1, kb_1_2, kb_1_3, kb_1_4)
        return kb

    elif where_call == 'car_company':
        kb_2_0 = types.InlineKeyboardButton(text=cars_company_dict[0], callback_data=f'{cars_company_dict[0]}_1')
        kb_2_1 = types.InlineKeyboardButton(text=cars_company_dict[1], callback_data=f'{cars_company_dict[1]}_1')
        kb_2_2 = types.InlineKeyboardButton(text=cars_company_dict[2], callback_data=f'{cars_company_dict[2]}_1')
        kb_2_3 = types.InlineKeyboardButton(text=cars_company_dict[3], callback_data=f'{cars_company_dict[3]}_1')
        kb_2_4 = types.InlineKeyboardButton(text=cars_company_dict[4], callback_data=f'{cars_company_dict[4]}_1')
        kb_2_5 = types.InlineKeyboardButton(text=cars_company_dict[5], callback_data=f'{cars_company_dict[5]}_1')
        kb_2_6 = types.InlineKeyboardButton(text=cars_company_dict[6], callback_data=f'{cars_company_dict[6]}_1')
        kb_2_7 = types.InlineKeyboardButton(text=cars_company_dict[7], callback_data=f'{cars_company_dict[7]}_1')
        kb_2_8 = types.InlineKeyboardButton(text=cars_company_dict[8], callback_data=f'{cars_company_dict[8]}_1')
        kb.add(kb_2_0, kb_2_1, kb_2_2, kb_2_3, kb_2_4, kb_2_5, kb_2_6, kb_2_7, kb_2_8)
        return kb
    for i in range(len(cars_company_dict)):
        if where_call == f'car_body_type_{cars_company_dict[i]}':
            kb_3_1 = types.InlineKeyboardButton(text='Купе', callback_data=f'{cars_company_dict[i]}_1_0')
            kb_3_2 = types.InlineKeyboardButton(text='Джип', callback_data=f'{cars_company_dict[i]}_1_1')
            kb_3_3 = types.InlineKeyboardButton(text='Седан', callback_data=f'{cars_company_dict[i]}_1_2')
            kb.add(kb_3_1, kb_3_2, kb_3_3)
            return kb


@bot.message_handler(commands=['start', 'help'])
def category(message):
    bot.reply_to(message, "Сделайте выбор парсера!", reply_markup=keyboard('start'))


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):

    for i in range(len(cars_company_dict)):
        if call.data == 'auto.ru':
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text='Сделайте выбор марки машины!', reply_markup=keyboard('car_company'))
        elif call.data == 'hh.ru':
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text='Напишите проф.область (прим.: аналитик) !')
            @bot.message_handler(content_types=['text'])
            def get_user_text(message):
                proforientation = message.text
                data = HeadHunter(proforientation)

                kolvo = {0, 1}
                for i in kolvo:
                    name = data.iat[i, 2]
                    link = data.iat[i, 19]
                    employer1 = data.iat[i, 21]
                    employer = employer1['name']
                    hh_response = f'Вакансия:{name}, ссылка: {link}, компания: {employer} '
                    bot.send_message(call.message.chat.id, hh_response)

                file_hh = open('hh_data.xlsx', 'rb')
                bot.send_message(call.message.chat.id,
                                     'Выше указаны две вакансии для примера.')
                bot.send_message(call.message.chat.id,
                                     'Ниже вы найдете полный список вакансий по вашему запросу:')
                bot.send_document(chat_id=call.message.chat.id, document=file_hh)

        elif call.data == 'yandex_realty_':
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text='Вот список новых объявлений о сдаче недвижимости в аренду!')
            yandex_realty()
        elif call.data == 'avito_realty_':
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text='Вот список новых объявлений о сдаче недвижимости в аренду!')
            avito_realty()
        elif call.data == f'{cars_company_dict[i]}_1':
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text='Сделайте выбор кузова:', reply_markup=keyboard(f'car_body_type_{cars_company_dict[i]}'))
        elif call.data == f'{cars_company_dict[i]}_1_0':
            car_parsingReply = get_cars_info(i, 0)
            bot.send_message(call.message.chat.id, 'Выше пример по вашему запросу')
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=car_parsingReply)
            file = open('auto.csv', 'rb')
            bot.send_message(call.message.chat.id, 'Здесь вы найдете список машин и их характеристик по вашему запросу:')
            bot.send_document(chat_id=call.message.chat.id, document=file)
            bot.send_message(call.message.chat.id, 'А здесь вы найдете среднюю цену на авто по годам:')
            price_response1 = get_data_price()
            bot.send_message(call.message.chat.id, price_response1.to_string(index=False))
            bot.send_message(call.message.chat.id, 'А здесь вы найдете средний пробег у авто по годам:')
            milage_response1 = get_data_milage()
            bot.send_message(call.message.chat.id, milage_response1.to_string(index=False))

        elif call.data == f'{cars_company_dict[i]}_1_1':
            car_parsingReply = get_cars_info(i, 1)
            bot.send_message(call.message.chat.id, 'Выше пример по вашему запросу')
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=car_parsingReply)
            file = open('auto.csv', 'rb')
            bot.send_message(call.message.chat.id, 'Здесь вы найдете список машин и их характеристик по вашему запросу:')
            bot.send_document(chat_id=call.message.chat.id, document=file)
            bot.send_message(call.message.chat.id, 'А здесь вы найдете среднюю цену на авто по годам:')
            price_response2 = get_data_price()
            bot.send_message(call.message.chat.id, price_response2.to_string(index=False))
            bot.send_message(call.message.chat.id, 'А здесь вы найдете средний пробег у авто по годам:')
            milage_response2 = get_data_milage()
            bot.send_message(call.message.chat.id, milage_response2.to_string(index=False))

        elif call.data == f'{cars_company_dict[i]}_1_2':
            car_parsingReply = get_cars_info(i, 2)
            bot.send_message(call.message.chat.id, 'Выше пример по вашему запросу')
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=car_parsingReply)
            file = open('auto.csv', 'rb')
            bot.send_message(call.message.chat.id, 'Здесь вы найдете список машин и их характеристик по вашему запросу:')
            bot.send_document(chat_id=call.message.chat.id, document=file)
            bot.send_message(call.message.chat.id, 'А здесь вы найдете среднюю цену на авто по годам:')
            price_response3 = get_data_price()
            bot.send_message(call.message.chat.id, price_response3.to_string(index=False))
            bot.send_message(call.message.chat.id, 'А здесь вы найдете средний пробег у авто по годам:')
            milage_response3 = get_data_milage()
            bot.send_message(call.message.chat.id, milage_response3.to_string(index=False))


bot.polling(none_stop=True)
