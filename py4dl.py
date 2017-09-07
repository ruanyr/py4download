#! /usr/bin/env python

#--coding:utf-8--
#-*- coding:utf-8 -*-

import os
import xml.dom.minidom as dom
import threading
import re
import http.client as httpclient
import urllib.parse as parse
import time
import sys
import math

####################################################################################

__all_config = {"thread-size" : 3, "method" : "GET", "format" : ""}
__all_headers = {}
__all_res = {}  #保存资源，结构为: <资源地址, 所属文件夹>


def getHeaders():
    return __all_headers


def getProperty(name):
    return __all_config.get(name, None)


def initConf(confile = "config.xml"):
    """
    Load configuration file, if no configuration file specified then seek for default file 'config.xml'.\n
    :param confile: location of configuration file
    """
    if confile == "" or confile == None:
        confile = "config.xml"
    try:
        domTree = dom.parse(confile)
        root = domTree.documentElement
        rootName = root.nodeName
        if(rootName != "py4d"):
            print("Configuration file is broken:root element must be '<py4d>'!")
        __parsePropertyElement(root.getElementsByTagName("property"))
        headersTags = root.getElementsByTagName("headers")
        if len(headersTags) > 0:
            for headerTag in headersTags:
                headers = headerTag.getElementsByTagName("header")
                if len(headers) > 0:
                    __parseHeaders(headers)
    except Exception as ex:
        print("Can not parse config file '" + confile + "' due to:" + str(ex))
        sys.exit(1)
    finally:
        __searchTxtFileAndCreateFolder()


def getAllResources():
    return __all_res


def __createDir4TXT(name):
    """
    为txt文本文件创建对应的下载目录
    """
    pass
    dotpos = name.rindex(".")
    return name[0:dotpos]


def __searchTxtFileAndCreateFolder():
    """
    寻找程序目录下的TXT文件并为之创建下载目录
    """
    files = listFiles("./")
    for file in files:
        if file["type"] == "file" and file["name"].lower().endswith(".txt"):
            dirName = __createDir4TXT(file["name"])
            if not os.path.exists(dirName):
                print("\n-> 创建下载目录:" + dirName)
                os.mkdir(dirName)
            __loadResources(file["absolutepath"], dirName)


def __addResource(res, dirName):
    if res and res.strip() != "":
        __all_res[res.strip()] = dirName


def __loadResources(path, dirName):
    """
    从文本文件读取下载连接
    """
    pass
    file = open(path, "r")
    res = "_"
    while res:
        res = file.readline()
        __addResource(res, dirName)
    setTotalLinks(len(__all_res))

def __parsePropertyElement(properties):
    """
    Load properties from configuration file.
    :param properties:
    :return:
    """
    global __all_config
    if properties and len(properties) > 0:
        for prop in properties:
            name = prop.getAttribute("name")
            value = prop.getAttribute("value")
            if name == "thread-size":
                if not re.match(r"[0-9]{1,3}", value):
                    value = "1"
                __addProperty(name, value)
            elif name == "follow":
                if not re.match("true", value, re.I) and not re.match("false", value, re.I):
                    value = "false"
                __addProperty(name, value.lower())
            elif name == "format":
                value = value.strip()
                __addProperty(name, value)
            elif name == "connect-timeout":
                if not re.match(r"[0-9]+", value):
                    value = "0"
                __addProperty(name, value)
            elif name == "read-timeout":
                if not re.match(r"[0-9]+", value):
                    value = "0"
                __addProperty(name, value)
            elif name == "method":
                if not re.match("get", value, re.I) and not re.match("post", value, re.I):
                    value = "GET"
                __addProperty(name, value.upper())

    #print(__all_config)


def __parseHeaders(headers):
    """
    Load headers from configuration file.
    """
    global __all_headers
    if headers and len(headers) > 0:
        for header in headers:
            name = header.getElementsByTagName("name")[0].childNodes[0].data
            value = header.getElementsByTagName("value")[0].childNodes[0].data
            __addHeader(name, value)
    #print(__all_headers)


def __addProperty(name, value):
    """
    Add properties
    :param name: property name
    :param value: property value
    """
    __all_config[name] = value


def __addHeader(name, value):
    """
    Add request headers
    :param name: header name
    :param value: header value
    """
    __all_headers[name] = value




####################################################################################


def listFiles(path):
    files = []
    for parent, dirnames, filenames in os.walk(path):
        for name in dirnames:
            files.append({"absolutepath": os.path.join(parent, name), "name": name, "size": 0, "type": "dir", "lastmod": os.stat(os.path.join(parent, name)).st_mtime})
        for name in filenames:
            files.append({"absolutepath": os.path.join(parent, name), "name": name, "size": os.path.getsize(os.path.join(parent, name)), "type": "file", "lastmod":os.stat(os.path.join(parent, name)).st_mtime})
        return files
    return files


####################################################################################


__host_regex = "http[s]?://([^/]+)(/.)*"


def parseHost(url):
    """
    从链接解析主机地址（或域名）
    """
    global __host_regex
    matchedhost = re.match(__host_regex, url)
    if matchedhost:
        return matchedhost.group(1)
    else:
        None


def _wrapHeaders(conn):
    """
    将header封装进请求
    """
    headers = getHeaders()
    if len(headers) > 0:
        for name, value in headers.values():
            conn.putheader(name, value)


def __tranform_link_2_filename(url):
    """
    将下载链接转换为文件名，一个链接去掉特殊字符能够对应唯一的文件名。
    """
    url = url.strip()
    fn = url.replace("\\", "")\
    .replace("/", "_L")\
    .replace("&", "_A")\
    .replace("?", "_Q")\
    .replace(":", "")\
    .replace("<", "")\
    .replace(">", "")\
    .replace("*", "")\
    .replace("\"", "")\
    .replace("|", "I")\
    .replace(" ", "")
    return fn

def _parsePostedRequest(url):
    """
    如果下载需要使用POST请求，将参数写入Request Body传给服务器。
    url的形式类似：
    http://www.xxx.com/getres?resid=xxx&arg=xxx
    :return:
    """
    __qindex = url.find("?")
    if __qindex != -1:
        reqURL = url[0 : __qindex]
        reqParams = url[__qindex + 1:]
        reqParamsData = {}
        for attr_str in reqParams.split("&"):
            attrs = parse.splitvalue(attr_str)
            reqParamsData[attrs[0]] = attrs[1]

        return reqURL, parse.urlencode(reqParamsData).encode("utf-8")
    return url, ""

def _download(url, dirName, retrytime):
    if retrytime > 3:
        addFailed()
        addFinished()
        return
    conn = None
    __reqURL = ""
    __reqParams = ""
    if getProperty("method").upper() == "POST":
        __reqURL, __reqParams = _parsePostedRequest(url)
    if url.startswith("http://"):
        conn = httpclient.HTTPConnection(parseHost(url))
    elif url.startswith("https://"):
        conn = httpclient.HTTPSConnection(parseHost(url))
    else:
        raise Exception("No protocol.")
    headers = getHeaders()  # 公共header
    #conn.set_debuglevel(True)
    savefilename = __tranform_link_2_filename(url)
    tmpfilename = savefilename + ".tmp"
    extFormat = getProperty("format")
    if extFormat:
        extFormat = "." + extFormat
    else:
        extFormat = ""
    fullfilepath = os.path.abspath(dirName + "/" + savefilename + extFormat)
    fulltmpfilepath = os.path.abspath(dirName + "/" + tmpfilename + extFormat)
    if os.path.exists(fullfilepath):
        #print("资源：" + url + "已存在")
        addFinished()  # 下载完成数+1
        return
    # 如果临时文件存在那么尝试断点下载，如果服务器返回的header响应正确，
    # 则向临时文件追加字节，否则覆盖文件
    downed_len = 0
    if os.path.exists(fulltmpfilepath):
        downed_len = os.path.getsize(fulltmpfilepath)
        headers["Range"] = "bytes=" + str(downed_len) + "-"
    headers["Connection"] = "keep-alive"
    conn.connect()
    savefile = None
    #print("下载文件位置：" + os.path.abspath(dirName + "/" + savefilename))
    buf_len = 1024 * 2  # 每次读取的缓冲区大小, 同时分段读取方便控制下载速度

    try:
        if getProperty("method").upper() == "GET":
            conn.request(getProperty("method"), url, None, headers)
        else:
            headers["Content-Length"] = len(__reqParams)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            conn.request(getProperty("method"), __reqURL, __reqParams, headers)
        resp = conn.getresponse()
    except Exception as e:
        print(e)
        try:
            resp.close()
            conn.close()
        except Exception as ex:
            pass
        _download(url, dirName, retrytime + 1)
        return

    #print("临时文件:" + fulltmpfilepath)
    # 获取响应，判断资源是否支持断点续传================================================bug
    contentrange = resp.getheader("Content-Range", default="")
    #print(resp.getheaders())
    if resp.getcode() != 200 and resp.getcode() != 206:
        try:
            resp.close()
            conn.close()
        except Exception as ex:
            pass
        _download(url, dirName, retrytime + 1)
        return
    if resp.getcode() == 206:
        #print("支持断点续传：" + url)
        savefile = open(fulltmpfilepath, "ab")
    else:
        #print("不支持断点续传：" + url)
        savefile = open(fulltmpfilepath, "wb")

    try:

        bs = resp.read(buf_len)
        while bs:
            savefile.write(bs)
            updateBytes(len(bs))
            bs = not resp.isclosed() and resp.read(buf_len) or b""

        if bs:
            savefile.write(bs)
            updateBytes(len(bs))
        savefile.close()
        os.rename(fulltmpfilepath, fullfilepath)
        addFinished()   # 下载完成数+1
        resp.close()
        conn.close()
    except Exception as ex:
        print(str(ex))
        try:
            resp.close()
            conn.close()
        except Exception:
            pass
        _download(url, dirName, retrytime + 1)


class DownloadTask(threading.Thread):

    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
        self.url = None
        self.dirName = None
        self.__runningflag = threading.Event()
        self.__runningflag.clear()

    def getName(self):
        return self.name

    def __wakeup(self):
        """
        唤醒线程
        :return:
        """
        self.__runningflag.set()

    def __pause(self):
        """
        暂停线程
        """
        #print(self.name + " - 暂停")
        self.__runningflag.clear()
        returnThread(self)

    def assignTask(self, url, dirName):
        """
        分配下载任务并唤醒线程
        """
        self.url = url
        self.dirName = dirName
        #print(self.name + " - 唤醒")
        self.__wakeup()

    def run(self):
        #print("线程已被创建：" + self.name)
        self.__runningflag.wait()
        while True:
            #print(self.name + " - 开始下载文件：" + self.url)
            _download(self.url, self.dirName, 0)
            #print(self.name + " - 下载完成:" + self.url)
            self.__pause()
            self.__runningflag.wait()



####################################################################################


# 线程池
_pool = []


def initPool():
    print("-> 初始化线程池")
    print("-> 线程池大小:" + getProperty("thread-size"))
    poolsize = int(getProperty("thread-size"))
    for i in range(0, poolsize):
        thread = DownloadTask("Download-Thrad-" + str(i))
        thread.start()
        _pool.append(thread)


def getThread():
    while len(_pool) == 0:
        time.sleep(10)
    return _pool.pop()

def returnThread(thread):
    _pool.insert(0, thread)


####################################################################################



"""
下载数据统计
"""
# 下载链接总数
__totallinks = 0
# 已下载字节数
__downloadbytes = 0
# 已下载完成数
__finished = 0
# 下载失败数
__failed = 0
# 上一秒内下载总字节数
__last_sec_total_bytes = 0
# 下载总字节数
__total_bytes = 0

# 开始下载时间戳
_starttime = time.time()



def setTotalLinks(total):
    global __totallinks
    __totallinks = total


def _getTotalLinks():
    return __totallinks


def addFinished():
    global __finished
    __finished += 1

def addFailed():
    global __failed
    __failed += 1

def getFailed():
    global __failed
    return __failed

def _getFinished():
    return __finished


def updateBytes(len):
    global __downloadbytes, __last_sec_total_bytes, __total_bytes
    __downloadbytes += len
    __last_sec_total_bytes += len
    __total_bytes += len


def getTotalDownloadBytes():
    global __total_bytes
    return __total_bytes

def human_readable_filesize(size):
    if size < 1024:
        return str(size) + "B"
    elif size < 1048567:
        return '{:.2f}'.format(size / 1024) + "KB"
    elif size < 1073741824:
        return '{:.2f}'.format(size / 1048567) + "MB"
    else:
        return '{:.2f}'.format(size / 1073741824) + "GB"


def calculateSpeed():
    """
    计算下载速度\n
    :return: 下载速度(单位：s)，200KB/s、12MB/s等.
    """
    pass
    return human_readable_filesize(__last_sec_total_bytes) + "/s"


def calculateavgSpeed():
    """
    计算平均下载速度\n
    :return: 下载速度(单位：s)，200KB/s、12MB/s等.
    """
    __curttime = time.time()
    return human_readable_filesize(math.floor(__total_bytes / (__curttime - _starttime))) + "/s"


def resetLastSecondBytes():
    global __last_sec_total_bytes
    __last_sec_total_bytes = 0


def fixLength(num, width, fixchar="0"):
    """
    将数字补齐为固定宽度，不足宽度在前补齐
    """
    num = str(num)
    curlen = len(num)
    if curlen < width:
        for i in range(curlen, width):
            num = fixchar + num
    return num


__shine = True  #进度闪动

def _printProgress(finished, total):
    global __shine
    __percent = int(math.floor(finished / total * 15))
    __p = "["
    for i in range(0, __percent):
        __p += "="
    if __percent < 15:
        if __shine:
            __shine = False
            __p += ">"
        else:
            __shine = True
            __p += " "
    for i in range(__percent + 1, 15):
        __p += " "
    __p += "]"
    return __p


def _printPercent(finished, total):
    if finished == total:
        return "  100%"
    else:
        return '{:.2f}'.format(finished/total * 100) + "%"


def _getTotalDownload():
    return human_readable_filesize(getTotalDownloadBytes())


class MessageOutputTask(threading.Thread):

    def run(self):
        totallinks = _getTotalLinks()
        __total_width = len(str(totallinks))
        while True:
            finished = _getFinished()
            msgstr = ""
            msgstr += "| "
            msgstr += fixLength(finished, 6, "0")
            msgstr += "/"
            msgstr += fixLength(str(totallinks), 6, "0")
            msgstr += " |"
            msgstr += _printProgress(finished, totallinks)
            msgstr += "|  "
            msgstr += fixLength(_printPercent(finished, totallinks), 6, " ")
            msgstr += "|"
            msgstr += fixLength(calculateSpeed(), 12, " ")
            msgstr += "|"
            msgstr += fixLength(calculateavgSpeed(), 12, " ")
            msgstr += "|"
            msgstr += fixLength(_getTotalDownload(), 10, " ")
            msgstr += "|"
            msgstr += fixLength(getFailed(), 6, " ")
            msgstr += "|"
            print(msgstr, end='\r')
            resetLastSecondBytes()
            if finished == totallinks:
                print("\n+--------------------------------------------------------------------------------------+")
                print("\n-> 下载结束\t")
                print("-> 开始时间：" + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_starttime)))
                print("-> 结束时间：" + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
                break
            time.sleep(1)


def printWelcome():
    print("+--------------------------------------------------------------------------------------+")
    print("| Python Downloader powered by Tisnyi(hehety@outlook.com)                              |")
    print("| View on github : https://github.com/hetianyi/py4download                             |")
    print("|--------------------------------------------------------------------------------------|")
    print("|     总数      |       进度      | 百分比 |  即时速度  |  平均速度  | 下载流量 | 失败 |")
    print("|--------------------------------------------------------------------------------------|")


# 程序启动
def startDownload():
    """
    开始下载任务
    """
    initPool()  # 初始化线程池
    printWelcome()
    resources = getAllResources()   #获取所有的下载资源
    msgoutput = MessageOutputTask()    # 定时任务重设即时速度
    msgoutput.start()
    for url, dirName in resources.items():
        thread = getThread()
        thread.assignTask(url, dirName)


initConf()  #加载配置文件
startDownload()


