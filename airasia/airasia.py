# -*- coding: utf-8 -*-


import sys
import datetime
import requests
import json
import PyV8
import re
from lxml import etree

class airAsia(object):
    def __init__(self):
        self.req = requests.session()

    def select(self, o1, d1, dd1):
        req = self.req
        url = f'https://booking.airasia.com/Flight/Select?o1={o1}&d1={d1}&dd1={dd1}&culture=zh-CN&ADT=1&s=False&mon=true&cc=CNY'

        html = req.get(url, timeout=20)

        if 'var arg1' in html.text:
            print('step 1')
            pattern = re.compile(r"var arg1='(.*?)'")
            match = pattern.search(html.text)
            arg1 = match.group(1)

            pattern2 = re.compile(r'setCookie\("(.*?)"')
            match2 = pattern2.search(html.text)
            arg2 = match2.group(1)


            strtmp = getarg2(arg1)

            requests.utils.add_dict_to_cookiejar(req.cookies, {arg2: strtmp})
            requests.utils.add_dict_to_cookiejar(req.cookies, {"i10c_waited": "true"})
            html = req.get(url)

        if 'i10c_waited' in html.text:
            print('step 2')
            requests.utils.add_dict_to_cookiejar(req.cookies, {"i10c_waited": "true"})
            html = req.get(url, allow_redirects=False, timeout=20)

        if '<h2>Object moved to <a href="/Flight/Select">here</a>.</h2>' in html.text:

            html = req.get(url, allow_redirects=False, timeout=20)


        if 'noscript' in html.text:
            print('ok,find it')

        else:
            print('not found')

        # var json = JSON.parse\("(.*)"\)
        pattern = re.compile('var json = JSON.parse\("(.*)"\)', re.I)
        match = pattern.search(html.text)
        js = match.group(1)
        print(js)
        jsobj = json.loads(js.replace('\\"', '"'))

        ecommerce = jsobj['ecommerce']

        htmlobj = etree.HTML(html.text)
        radios = htmlobj.xpath('//input[@class="square-radio radio-markets"]')

        dic2 = {}
        for r1 in radios:
            id = r1.attrib['data-json']
            data_json = r1.attrib['data-json']
            productclass = r1.attrib['data-productclass']
            adt = r1.attrib['data-adt']
            chd = r1.attrib['data-chd']
            cur = r1.attrib['data-cur']

            # print data_json
            data_json_obj = json.loads(data_json)
            position = data_json_obj[0]['position']
            value = r1.attrib['value']
            flightinfo = value.split('|')[1]
            sflight = flightinfo.split('^')
            deptime = sflight[0].split('~')[5]
            arrtime = sflight[len(sflight) - 1].split('~')[7]
            # print deptime,arrtime
            depdate = datetime.datetime.strptime(deptime, '%m/%d/%Y %H:%M')
            arrdate = datetime.datetime.strptime(arrtime, '%m/%d/%Y %H:%M')
            deptime = depdate.strftime('%Y-%m-%d %H:%M:%S')
            arrtime = arrdate.strftime('%Y-%m-%d %H:%M:%S')

            # 查询票价及税费
            postdata = {'SellKeys[]': value, 'MarketValueBundles[]': 'false',
                        'MarketProductClass[]': productclass, 'MarketUpgradePrice[]': '0',
                        'SaveMarketBundlesSession': 'false'}
            poststr = ''
            for key in postdata:
                poststr += key + '=' + postdata[key] + '&'
            poststr = poststr.strip('&')
            url2 = 'https://booking.airasia.com/Flight/PriceItinerary?' + poststr


            priceaddobj = htmlobj.xpath('//div[@data-bundleremove="trip_0_date_0_flight_0_fare_0"]')

            upgradeprice = []
            if priceaddobj:
                for p1 in priceaddobj:
                    dic3 = {}
                    if 'data-upgradeprice' in p1.attrib:
                        dic3['price'] = float(p1.attrib['data-upgradeprice'])
                        # upgradeprice.append({'price':p1.attrib['data-upgradeprice']})

                        # print etree.tostring(p2)
                    elif p1.xpath('div/input[@type="radio"]'):
                        p11 = p1.xpath('div/input[@type="radio"]')[0]
                        # upgradeprice.append({'price': p11.attrib['data-upgradeprice']})
                        dic3['price'] = float(p11.attrib['data-upgradeprice'])
                    pn = p1.getnext()
                    pp = p1.getprevious()
                    if pp.xpath('div[@class="text-container"]/h1'):
                        header = pp.xpath('div[@class="text-container"]/h1')[0].text

                        dic3['header'] = header.strip()
                    if pn.xpath('div[@class="bundle-details-body"]'):
                        xh = 0
                        bodystr = ''
                        for bodyitem in pn.xpath('div[@class="bundle-details-body"]/div[@class="bundle-detail-item"]'):
                            xh += 1
                            spanstr = ''
                            for span in bodyitem.xpath('div/span'):
                                if span.text:
                                    spanstr += span.text.strip()
                            bodystr += spanstr + ';'
                        dic3['body'] = bodystr

                    upgradeprice.append(dic3)

            dic2[position] = {'adt': adt, 'chd': chd, 'cur': cur, 'deptime': deptime, 'arrtime': arrtime,
                              'upgradeprice': upgradeprice}

        result = []
        dic = {}
        for impressions in ecommerce['impressions']:
            position = impressions['position']
            dimension6 = impressions['dimension6']  # "Flight 1"
            ftype = impressions['dimension1']  # dimension1: "OW"
            cabin = impressions['dimension4']  # dimension4: "L":貌似舱位
            if len(cabin) == 2:
                continue
            allline = impressions['dimension13']  # PEK-(KUL)-DPS
            dep = allline[0:3]
            arr = allline[-3:]
            ltype = impressions['dimension15']
            tracity = ''  # 中转
            if ltype == 'Fly-Through':
                tracity = allline.split('-')[1].replace('(', '').replace(')', '')
            day = impressions['dimension5']  # 2018-02-26

            price = float(impressions['price'])
            brand = impressions['brand']  # AK：航空公司
            flightno = impressions['dimension16']  # dimension16 : "AK175"

            key = str(position) + '_' + cabin
            if key in dic:
                dic[key]['price'] += price
                dic[key]['brand'] += '-' + brand
                dic[key]['flightno'] += '-' + flightno
            else:
                dic[key] = {'price': price,
                            'brand': brand,
                            'flightno': flightno,
                            'ftype': ftype,
                            'cabin': cabin,
                            'dep': dep, 'arr': arr, 'tracity': tracity, 'day': day,
                            'adt': dic2[position]['adt'],
                            'chd': dic2[position]['chd'],
                            'cur': dic2[position]['cur'],
                            'deptime': dic2[position]['deptime'],
                            'arrtime': dic2[position]['arrtime'],
                            'upgradeprice': dic2[position]['upgradeprice']}

        for key in dic:
            result.append(dic[key])

        print(json.dumps(result, ensure_ascii=False))
        return result
        '''
        htmlobj=etree.HTML(html.text)
        trs1=htmlobj.xpath('//table[@class="table avail-table"]/tbody/tr[@class="fare-light-row" or @class="fare-dark-row"]')
        for tr1 in trs1:
            tds = tr1.xpath('td')
            #print len(tds)
            if len(tds)>1:
                td0 = tds[0]
                avail_table_info = td0.xpath('table[@class="avail-table-info"]')[0]
                #print avail_table_info
                avail_table_detail_table=avail_table_info.xpath('tr/td/table[@class="avail-table-detail-table"]')[0]
                #print avail_table_detail_table
                fare_row=avail_table_detail_table.xpath('tr')
                print len(fare_row)
                '''

    def login(self, usr, pwd):
        # url='https://ssor.airasia.com/sso/v2/authorization/by-credentials?clientId=AA001AP'
        url = 'https://ssor.airasia.com/config/v2/clients/by-origin'

        header = {'content-type': 'application/json',
                  'Referer': 'https://www.airasia.com/cn/zh/home.page?cid=1',
                  'accept': 'application/json',
                  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.110 Safari/537.36',
                  'Accept-Encoding': 'gzip, deflate, sdch, br',
                  'Accept-Language': 'zh-CN,zh;q=0.8',
                  'Connection': 'keep-alive',
                  'Accept': 'application/json',
                  'Origin': 'https://www.airasia.com'
                  }
        html = self.req_login.get('https://ssor.airasia.com/config/v2/clients/by-origin', headers=header, verify=False)

        obj = html.json()
        if not obj:
            return None
        if not 'id' in obj:
            return None
        clientId = obj['id']
        apiKey = obj['apiKey']

        url = 'https://ssor.airasia.com/sso/v2/authorization/by-credentials?clientId=' + clientId
        jsonobj = {"username": usr, "password": pwd}
        header['x-api-key'] = apiKey

        html = self.req_login.post(url, json=jsonobj, verify=False, headers=header)

        obj2 = html.json()
        userId = obj2['userId']
        accessToken = obj2['accessToken']

        url = 'https://ssor.airasia.com/um/v2/users/' + userId
        header['x-aa-client-id'] = clientId
        header['authorization'] = accessToken

        html = self.req_login.get(url, headers=header, verify=False)


    def getarg2(arg1):
        js_func = '''
                      function getit(aaa)
              { var _0x5e8b26 = '3000176000856006061501533003690027800375';

            		String['prototype']['hexXor'] = function(_0x4e08d8) {
            			var _0x5a5d3b = '';
            			for (var i = 0x0; i < this['length'] && i < _0x4e08d8['length']; i += 0x2) {
            				var _0x401af1 = parseInt(this['slice'](i, i + 0x2), 0x10);
            				var _0x105f59 = parseInt(_0x4e08d8['slice'](i, i + 0x2), 0x10);
            				var _0x189e2c = (_0x401af1 ^ _0x105f59)['toString'](0x10);
            				if (_0x189e2c['length'] == 0x1) {
            					_0x189e2c = '0' + _0x189e2c;
            				}
            				_0x5a5d3b += _0x189e2c;
            			}
            			return _0x5a5d3b;
            		};

            		String['prototype']['unsbox'] = function() {
            			var _0x4b082b = [0xf, 0x23, 0x1d, 0x18, 0x21, 0x10, 0x1, 0x26, 0xa, 0x9, 0x13, 0x1f, 0x28, 0x1b, 0x16, 0x17, 0x19, 0xd, 0x6, 0xb, 0x27, 0x12, 0x14, 0x8, 0xe, 0x15, 0x20, 0x1a, 0x2, 0x1e, 0x7, 0x4, 0x11, 0x5, 0x3, 0x1c, 0x22, 0x25, 0xc, 0x24];
            			var _0x4da0dc = [];
            			var _0x12605e = '';
            			for (var _0x20a7bf = 0x0; _0x20a7bf < this['length']; _0x20a7bf++) {
            				var _0x385ee3 = this[_0x20a7bf];
            				for (var _0x217721 = 0x0; _0x217721 < _0x4b082b['length']; _0x217721++) {
            					if (_0x4b082b[_0x217721] == _0x20a7bf + 0x1) {
            						_0x4da0dc[_0x217721] = _0x385ee3;
            					}
            				}
            			}
            			_0x12605e = _0x4da0dc['join']('');
            			return _0x12605e;
            		};

            		var _0x23a392 = aaa['unsbox']();
            		arg2 = _0x23a392['hexXor'](_0x5e8b26);
            		return arg2;
              }
                    '''

        ctxt = PyV8.JSContext()
        ctxt.enter()
        ctxt.eval(js_func)
        getit = ctxt.locals.getit
        str = getit(arg1)
        return str

if __name__=='__main__':

    aa=airAsia()
    flightlist=aa.select('CSX','KUL','2018-06-23')
    print (json.dumps(flightlist))