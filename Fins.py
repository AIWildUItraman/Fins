from socket import *
import threading
import time
import re
import struct
import string
import platform
import os
import fcntl, struct
 

typeBool    =   'Bool'      #2个字节
typeShort   =   'Short'     #2个字节
typeUShort   =   'UShort'     #2个字节
typeInt     =   'Int'       #4个字节
typeFloat   =   'Float'     #4个字节
typeString  =   'String'    #字符串长度
typeBit     =   'Bit'       #


#cip客户端
class Fins():
    # exit = QtCore.pyqtSignal()  # 信号  √
    def __init__(self,aimIp,aimPort):
        # 数据部分
        print('PLC IP:', aimIp) 
        print('PLC port:', aimPort)

        self.sock = socket(AF_INET, SOCK_STREAM)      #用于保存socket套接字

        #网络状态由这两个共同决定，握手失败主动断开，数据发送不符合规格，主动断开
        self.connectState = False       # 网络是否连接成功
        self.handshakeState = False       # 握手成功标志

        self.serverIp = ''  # 这个用来保存服务器的IP节点--组帧需要使用
        self.clientIp = ''  # 这个用来保存客户端的IP节点--组帧需要使用

        #错误码
        self.finsErrorCode = {
            b'\x00\x00\x00\x00': "Normal",
            b'\x00\x00\x00\x01': "The header is not 'Fins'",
            b'\x00\x00\x00\x02': "The data length is too long",
            b'\x00\x00\x00\x03': "The command is not supported",
            b'\x00\x00\x00\x20': "All connections are in use",
            b'\x00\x00\x00\x21': "The specified node is already connected",
            b'\x00\x00\x00\x22': "Attempt to access a protected node from an unspecified IP address",
            b'\x00\x00\x00\x23': "The client FINS node address is out of range",
            b'\x00\x00\x00\x24': "The same FINS node address is being used by the client and server",
            b'\x00\x00\x00\x25': "All the node addresses available for allocation have been used",
        }

        self.lock = threading.Lock()    #它是一个基本的锁对象，每次只能锁定一次，其余的锁请求，需等待锁释放后才能获取
        #self.rlock = threading.RLock() #对于可重入锁，在同一个线程中可以对它进行多次锁定，也可以多次释放。如果使用 RLock，那么 acquire() 和 release() 方法必须成对出现。如果调用了 n 次 acquire() 加锁，则必须调用 n 次 release() 才能释放锁

        #获取当前系统的ip，目前支持Linux、Windows系统
        self.ipAddr = self.getSystemIp()
        # self.ipAddr = '192.168.1.100'
        print(self.ipAddr)
        if self.ipAddr == '':
            print('Check The Network')
            return
        
        self.initSys(aimIp,aimPort)

    # Fins协议,连接网络,发送握手帧  √
    # Ip Port   plc的 
    def initSys(self,Ip,Port):
        try:
            self.connectState = self.connect(Ip, Port)

            if self.connectState == True:
                handshakeFrame = self.createHandshake(self.ipAddr)
                self.sendFrame(handshakeFrame)
                self.recvMsg()
        except:
            print('function initSys error')

    ##连接服务器    √
    def connect(self, Ip, Port):
        try:
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.sock.settimeout(2)
            self.sock.connect((Ip, Port))
            return True
        except Exception:
            self.disConnect()
            print('function connect error')
            return False

    # √
    def disConnect(self):
        self.connectState = False
        self.handshakeState = False
        self.sock.close()
        print('网络连接失败')

    def getLinuxIp(self):
        try:
            ifname = 'eth0'
            s = socket(AF_INET, SOCK_DGRAM)
            ip = inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname[:15]))[20:24])

        except:
            ip = ''
        finally:
            s.close()
        return ip

    def getWindowsIp(self):
        try:
            ip = gethostbyname(gethostname())
            return ip
        except:
            return ''
        return ip

    def getSystemIp(self):
        sysType = platform.system()
        if sysType == 'Windows':
            print('Windows System')
            return self.getWindowsIp()
        elif sysType == 'Linux':
            print('Linux System')
            return self.getLinuxIp()
        else:
            print('Other System')
            return ''
    # 生成握手帧  
    # Ip  PLC的  
    def createHandshake(self, Ip):
        try:
            shakeHandsStr = '46494E530000000C0000000000000000000000'
            shakeHandsStr = bytes.fromhex(shakeHandsStr)
            shakeHandsStr += struct.pack('>b', int(Ip.split('.')[-1]))
            # print('要发送数据为：',shakeHandsStr)
            return shakeHandsStr
        except:
            print('function createHandshake error')

    # 发送函数 √
    def sendFrame(self, data):
        try:
            self.sock.send(data)
        except:
            self.disConnect()   #数据发送失败，则主动断开连接
            print('function sendFrame error')

    #  接收数据 √
    def recvMsg(self):       
        try:
            # 网络连接的时候这里是阻塞的,除非是接收到数据才会执行下一步
            data = self.sock.recv(1024)
            
            if data == "":
                self.disConnect()
            else:
                return self.handleData(data)
        except:
            print('function recvMsg error') #这里是由于超时引起的问题
            self.disConnect()
    # fins头 √
    def createFinsHeader(self, finsFrame):
        try:

            finsFrameLength = len(finsFrame)
            finsHeader = b'\x46\x49\x4e\x53'  
            finsHeader += struct.pack('>i', finsFrameLength + 8)
            
            finsHeader += b'\x00\x00\x00\x02'
            finsHeader += b'\x00\x00\x00\x00'
            finsHeader += finsFrame
            # print('Send Frame is:' , finsHeader)
            # print('length = ',len(finsHeader))
            return finsHeader
        except:
            print('function createFinsHeader error')

    # fins帧 √
    def createReadFinsFrame(self, addr, length):
        try:
            finsFrame = b'\x80\x00\x02\x00'  # FINS命令 固定
            finsFrame += struct.pack('>B', self.serverIp)
            finsFrame += b'\x00\x00'
            finsFrame += struct.pack('>B', self.clientIp)
            finsFrame += b'\x00\x00\x01\x01'
            finsFrame += b'\x82'        # 读地址区域代码(82表示读取的是DM区)   
            finsFrame += struct.pack('>h', addr)  #读 起始地址 D1  对应 0001
            finsFrame += b'\x00'    
            finsFrame += struct.pack('>h', length)   #读数据长度
            return finsFrame
        except:
            print('function createReadFinsFrame error')

    # fins帧
    def createWriteFinsFrame(self, addr, dataType, value):
        try:

            if dataType == 'Int':
                dataFrame = struct.pack('>i', value)
            elif dataType == 'Float':
                dataFrame = struct.pack('>f', value)

            finsFrame = b'\x80\x00\x02\x00'
            finsFrame += struct.pack('>B', self.serverIp)
            finsFrame += b'\x00\x00'
            finsFrame += struct.pack('>B', self.clientIp)
            finsFrame += b'\x00\x00\x01\x02'
            finsFrame += b'\x82'  
            finsFrame += struct.pack('>h', addr)
            finsFrame += b'\x00'
            finsFrame += struct.pack('>h', int(len(dataFrame)/2))
            finsFrame += dataFrame
            return finsFrame
        except:
            print('function createWriteFinsFrame error')

    def reMatch(self,addr):
        try:
            return re.search(r'^D[0-9]*$', addr).group()
        except:
            return

    # 读取指定地址数据   √
    # addr      起始地址
    # length    读取字数量
    # 返回值       数据帧部分
    def finsRead(self, addr, length):
        self.lock.acquire()
        try:
            if self.connectState == True and self.handshakeState == True:
                if self.reMatch(addr) != "":
                    finsReadFrame = self.createFinsHeader(self.createReadFinsFrame(int(self.reMatch(addr)[1:]), length))
                    self.sendFrame(finsReadFrame)
                    return self.recvMsg()
                else:
                    print('地址错误或不存在')
        except:
            print('function finsRead error')
        finally:
            self.lock.release()

    # 写指定地址数据
    # addr      起始地址
    # dataType    写入类型
    # value     值
    def finsWrite(self, addr, dataType, value):
        self.lock.acquire()
        try:
            if self.connectState == True and self.handshakeState == True:
                if self.reMatch(addr) != "":
                    finsWriteFrame = self.createFinsHeader(
                        self.createWriteFinsFrame(int(self.reMatch(addr)[1:]), dataType, value))
                    self.sendFrame(finsWriteFrame)
                    self.recvMsg()

                else:
                    print('地址错误或不存在')
        except:
            print('function finsWrite error')
        finally:
            self.lock.release()

    #addr   地址(这里只读取1个字的长度,即16位)
    #site   读取当前字节的位置
    #返回值    Bool类型的值
    def finsReadBit(self,addr,site):
        data = self.parseData(self.finsRead(addr, 1), typeShort)
        if ((data & (1<<site))>>site) == 1:
            return True
        else:
            return False

    # 位操作，写1、0
    # addr      地址  'D100'
    # value     值   0/1		1
    # site     当前地址的第几位操作  [0,15]	3
    # 这里一次读取出来的数据为两个字，所以需要处理
    def finsWriteBit(self,addr,value,site):
        try:
            #这里必须取无符号数据方可，否则当出现
            #例如0xffff这样的数据时，第一位被当作符号位，造成数据值转换出错，造成数据处理错误
            currData = struct.unpack('>H', self.finsRead(addr, 1))[0]

            if site >= 0 and site <=15:
                #读回来原来的数据并做移位处理
                a = self.operateBit(currData,value,site)
                #写入当前的数据
                self.finsWrite(addr,typeUShort,a)
            else:
                print('out of range')
        except:
            pass

    # 握手函数  √
    def handleHandshake(self, data, index):
        try:
            # 判断错误码信息
            if data[index:index + 4] in self.finsErrorCode:  # 错误码
                if data[index:index + 4] == b'\x00\x00\x00\x00':
                    print('握手成功')
                    self.handshakeState = True
                else:
                    print('error code is : ', self.finsErrorCode[data[index:index + 4]])
                    self.disConnect()
                    return
            index += 4

            # 客户端节点地址
            # print 'client ip is :',struct.unpack('>i',str(data[index:index+4]))[0]
            self.clientIp = data[index + 3]

            index += 4
            # 服务器节点地址
            # print 'server ip is',struct.unpack('>i',str(data[index:index+4]))[0]
            self.serverIp = data[index + 3]
            index += 4
        except:
            self.disConnect()
            print('function handleHandshake error')

    # √
    def handleDataFrame(self,data,index):
        try:
            # 判断错误码信息
            if data[index:index + 4] in self.finsErrorCode:  # 错误码
                if data[index:index + 4] != b'\x00\x00\x00\x00':
                    print('error code is : ', self.finsErrorCode[data[index:index + 4]])
                    self.disConnect()
                    return
            
            index += 4
            # FINS命令
            if data[index:index + 4] != b'\xc0\x00\x02\x00':
                print('FINS命令不正确')
                self.disConnect()
                return
            index += 4

            # IP地址
            # 这里先不管，好像IP地址和文档描述中存在差异，后期查阅资料补全，这里不检测
            index += 4

            # 读取数据命令
            if data[index:index + 4] == b'\x00\x00\x01\x01':
                pass
                print('读数据命令返回帧')
            elif data[index:index + 4] == b'\x00\x00\x01\x02':
                pass
                print('写数据命令返回帧')
            index += 4

            # 通讯状态
            if data[index:index + 2] != b'\x00\x00' and data[index:index + 2] != b'\x00\x40':
                pass
                print('通讯异常')
                print(data)

                self.disConnect()
                return
            index += 2

            # 数据
            realDate = data[index:]

            return realDate
            # 解析完成
        except:
            print('function handleDataFrame error')

    # 处理接收的帧   √
    def handleData(self,data):
        try:
            index = 0
            # 头部     4
            if data[0:4] != b'\x46\x49\x4e\x53':
                print('不是FINS协议命令')
                self.disConnect()
                return
            
            index += 4
            # print('帧长度', len(data) - 8, data[index:index + 4], data[index + 3])
            
            if (len(data) - 8) != data[index + 3]: 
                print('接收长度错误')
                self.disConnect()
                return
            
            index += 4
            # 判断帧类型
            if data[index:index + 4] == b'\x00\x00\x00\x01':  # 握手帧返回
                index += 4

                self.handleHandshake(data, index)
            elif data[index:index + 4] == b'\x00\x00\x00\x02':  # 读写指令
                index += 4
                realDate = self.handleDataFrame(data, index)
                return realDate
        except:
            self.disConnect()
            print('function handleData error')

    #位操作函数
    #data   原数据
    #value  值
    #site	偏移位置
    def operateBit(self,data, value, site):
        if value == 1:  #置1
            return data | (1 << site)
        elif value == 0:    #置0
            return data & (~(1 << site))
        else:
            print('value is error')

if __name__ == '__main__':

    print('********enter FINS*************')
    aimIp = '192.168.1.90'
    aimPort = 9600
    f = Fins(aimIp,aimPort)

    
    while 1:
        j = 0
        if f.connectState == True:
            print('连接成功')
            f.finsWrite('D100', typeInt, 12)
            #读数据--最少读取一个字的长度数据
            print(struct.unpack('>i', f.finsRead('D100', 2)))

            # #写数据Int--目前仅实现了写单独一个数据
            # f.finsWrite('D100',typeInt,12)
            # # print(f.finsRead('D100', 2))
            #
            # #写数据Float
            # f.finsWrite('D100',typeFloat,12.23)
            # print(f.finsRead('D100', 2))

            

        break
        time.sleep(1)
    















