# encoding:utf-8

"""
wechat channel
"""
import datetime
import io

import time

import requests
import random
from bridge.context import *
from bridge.reply import *
from channel.chat_channel import ChatChannel
from channel.wechat.wechat_message import *
from common.expired_dict import ExpiredDict
from common.log import logger
from common.singleton import singleton
from common.time_check import time_checker
from config import conf, get_appdata_dir

from channel.wechat.iPadWx import iPadWx

@singleton
class WechatChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = []

    def __init__(self):
        super().__init__()
        self.receivedMsgs = ExpiredDict(60 * 60)
        self.auto_login_times = 0
        self.bot=iPadWx()
        if self.bot.is_login:
            self.init_load()  # 确保初始化代码在实例创建时执行

    def init_load(self):
        '''
        初始化加载
        '''
        if not self.bot.is_login or not self.bot.wx_id:
            logger.error("微信未登录或未获取到wx_id，无法初始化配置")
            return False

        # 获取机器人信息
        time.sleep(random.randint(0,4))
        bot_info = self.bot.get_robot_info()
        if bot_info:
            if bot_info['code'] == 9001:
                time.sleep(random.randint(0, 4))
                bot_info = self.bot.get_robot_info()
            if bot_info['code'] != 0:
                logger.error(f"获取机器人信息失败: {bot_info}")
                return False

        # 获取用户信息
        time.sleep(2)
        user_info = self.bot.get_user_info()
        if not user_info:
            logger.error("获取用户信息失败")
            return False
            
        if user_info['code'] == 5001:
            logger.error(user_info)
            return False
        if user_info['code'] == 9001:
            time.sleep(random.randint(0, 4))
            user_info = self.bot.get_user_info()
        if user_info['code'] != 0:
            logger.error(f"获取用户信息失败: {user_info}")
            return False

        # 设置基本信息
        max_group = int(user_info['data'].get('max_group', 10))
        whitelisted_group_ids = user_info['data'].get('whitelisted_group_ids', [])
        self.name = bot_info['data'].get('nickname', "")
        message_types_to_filter = user_info['data']['message_types_to_filter']
        self.user_id = bot_info['data']['id']

        # 检查机器人到期时间
        expiry_date = bot_info['data']['expiry_date']
        if expiry_date < datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
            logger.error(f"机器人到期时间{expiry_date}!!")
            return False

        # 检查回调URL
        config_callback_url = conf().get("http_hook")
        current_callback_url = user_info['data']['callback_url']
        if config_callback_url != "" and current_callback_url != config_callback_url:
            logger.error(f"机器人callback 不正确{config_callback_url}!!")
            self.bot.set_callback_url(config_callback_url)

        # 更新群信息
        update_group = True
        if update_group:
            groups = self.bot.get_device_room_list()
            if groups['code'] != 0:
                logger.error("获取设备群列表失败")
                return False

            groups2 = self.bot.get_room_list()
            if groups2['code'] == 0:
                # 合并群列表并去重
                merged_groups = set(groups["data"] + groups2["data"])

                # 更新群信息
                need_save = False
                for room_id in merged_groups:
                    if room_id not in self.bot.shared_wx_contact_list:
                        logger.info(f"群还未查询过{room_id}")
                        room_info = self.bot.get_room_info(room_id)
                        if room_info['code'] == 0:
                            iPadWx.shared_wx_contact_list[room_id] = room_info['data']
                            members = self.bot.get_chatroom_memberlist(room_id)
                            if members['code'] == 0:
                                iPadWx.shared_wx_contact_list[room_id]['chatRoomMembers'] = members['data']
                                logger.info(f"群还未查询过{room_id},名称{room_info['data']['nickName']}")
                                need_save = True
                                time.sleep(2)

                if need_save:
                    self.bot.save_contact()

                # 处理需要监控的群
                group_need_monitors = []
                group_name_white_list = conf().get("group_name_white_list")
                
                # 根据群名匹配需要监控的群
                for group_need_monitor in group_name_white_list:
                    for key, item in iPadWx.shared_wx_contact_list.items():
                        if (item and key.endswith("@chatroom") and 
                            item['chatRoomId'] != "" and item['nickName'] != "" and
                            item['nickName'].lower() == group_need_monitor.lower()):
                            if len(group_need_monitors) >= max_group:
                                logger.info(f"群监控数量超过{max_group}个,{group_need_monitor}，退出")
                                break
                            else:
                                group_need_monitors.append(key)

                # 根据群ID匹配需要监控的群
                group_name_white_roomid_list = conf().get("group_name_white_roomid_list", {})
                for group_id, group_name in group_name_white_roomid_list.items():
                    if group_id not in group_need_monitors:
                        if len(group_need_monitors) >= max_group:
                            logger.info(f"群监控数量超过{max_group}个，退出")
                            break
                        logger.debug(f"{group_id},{group_name}已加入监控")
                        group_need_monitors.append(group_id)

                # 处理ALL_GROUP配置
                if "ALL_GROUP" in group_name_white_list:
                    for room_id in groups['data']:
                        if room_id not in group_need_monitors and len(group_need_monitors) < max_group:
                            group_need_monitors.append(room_id)
                        if len(group_need_monitors) >= max_group:
                            break

                # 输出监控信息
                not_monitor = set(groups['data']) - set(group_need_monitors)
                logger.info(f"当前群{groups['data']}")
                logger.info(f"需要监控的群{group_need_monitors}")
                logger.info(f"不需要监控的群{not_monitor}")

                # 输出详细群信息
                for room_id in list(not_monitor):
                    logger.info(f"还未监控的群{room_id},群名{iPadWx.shared_wx_contact_list[room_id]['nickName']}")
                for room_id in list(group_need_monitors):
                    logger.info(f"监控的群{room_id},群名{iPadWx.shared_wx_contact_list[room_id]['nickName']}")

                # 设置群监听
                if group_need_monitors:
                    payload = {"group": group_need_monitors}
                    ret = self.bot.group_listen(payload=payload)
                    logger.info(f"group_listen ret:{ret}")
                else:
                    logger.info(f"没有群需要监控{group_need_monitors}")

        return True

    def startup(self):
        pass


        #port = conf().get("wechatipad_port", 5711)
        #self.init_load()

        #quart_app.run("0.0.0.0", port, use_reloader=False)


        # urls = (
        #     '/chat', 'channel.wechat.wechat_channel.WechatPadChannel'
        # )
        # app = web.application(urls, globals(), autoreload=False)
        # web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", port))

        # try:
        #     itchat.instance.receivingRetryCount = 600  # 修改断线超时时间
        #     # login by scan QRCode
        #     hotReload = conf().get("hot_reload", False)
        #     status_path = os.path.join(get_appdata_dir(), "itchat.pkl")
        #     itchat.auto_login(
        #         enableCmdQR=2,
        #         hotReload=hotReload,
        #         statusStorageDir=status_path,
        #         qrCallback=qrCallback,
        #         exitCallback=self.exitCallback,
        #         loginCallback=self.loginCallback
        #     )
        #     self.user_id = itchat.instance.storageClass.userName
        #     self.name = itchat.instance.storageClass.nickName
        #     logger.info("Wechat login success, user_id: {}, nickname: {}".format(self.user_id, self.name))
        #     # start message listener
        #     itchat.run()
        # except Exception as e:
        #     logger.exception(e)


    # handle_* 系列函数处理收到的消息后构造Context，然后传入produce函数中处理Context和发送回复
    # Context包含了消息的所有信息，包括以下属性
    #   type 消息类型, 包括TEXT、VOICE、IMAGE_CREATE
    #   content 消息内容，如果是TEXT类型，content就是文本内容，如果是VOICE类型，content就是语音文件名，如果是IMAGE_CREATE类型，content就是图片生成命令
    #   kwargs 附加参数字典，包含以下的key：
    #        session_id: 会话id
    #        isgroup: 是否是群聊
    #        receiver: 需要回复的对象
    #        msg: ChatMessage消息对象
    #        origin_ctype: 原始消息类型，语音转文字后，私聊时如果匹配前缀失败，会根据初始消息是否是语音来放宽触发规则
    #        desire_rtype: 希望回复类型，默认是文本回复，设置为ReplyType.VOICE是语音回复
    # def handle_single(self, cmsg: ChatMessage):
    #     # filter system message
    #     if cmsg.other_user_id in ["weixin"]:
    #         return
    #     if cmsg.ctype == ContextType.VOICE:
    #         if conf().get("speech_recognition") != True:
    #             return
    #         logger.debug("[WX]receive voice msg: {}".format(cmsg.content))
    #     elif cmsg.ctype == ContextType.IMAGE:
    #         logger.debug("[WX]receive image msg: {}".format(cmsg.content))
    #     elif cmsg.ctype == ContextType.PATPAT:
    #         logger.debug("[WX]receive patpat msg: {}".format(cmsg.content))
    #     elif cmsg.ctype == ContextType.TEXT:
    #         logger.debug("[WX]receive text msg: {}, cmsg={}".format(json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg))
    #     else:
    #         logger.debug("[WX]receive msg: {}, cmsg={}".format(cmsg.content, cmsg))
    #     context = self._compose_context(cmsg.ctype, cmsg.content, isgroup=False, msg=cmsg)
    #     if context:
    #         self.produce(context)
    def handle_group(self, cmsg: ChatMessage):
        #if cmsg.is_at and self.user_id in cmsg.at_list:
        if cmsg.ctype == ContextType.VOICE:
            logger.debug("[WX]receive voice for group msg: {}".format(cmsg.content))
            if cmsg.is_group:
                if conf().get("group_speech_recognition") != True:
                    logger.debug("[WX]group speech recognition is disabled")
                    return
            else:
                if conf().get("speech_recognition") != True:
                    logger.debug("[WX]speech recognition is disabled")
                    return
            logger.debug("[WX]receive voice for group msg: {}".format(cmsg.content))

        elif cmsg.ctype == ContextType.IMAGE:
            logger.debug("[WX]receive image for group msg: {}".format(cmsg.content))
        elif cmsg.ctype in [ContextType.JOIN_GROUP, ContextType.PATPAT, ContextType.ACCEPT_FRIEND, ContextType.EXIT_GROUP]:
            logger.debug("[WX]receive note msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.TEXT:
            #logger.debug("[WX]receive msg: {}, cmsg={}".format(json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg))
            pass
        elif cmsg.ctype == ContextType.FILE:
            logger.debug(f"[WX]receive attachment msg, file_name={cmsg.content}")
        elif cmsg.ctype == ContextType.XML:
            pass
            #logger.debug(f"[WX]receive XML msg")
            #logger.debug("[WX]receive XML msg for group: {}".format(cmsg.content))

        else:
            logger.debug("[WX]receive msg: {}".format(cmsg.content))
        reply_at = conf().get("reply_at",False)
        context = self._compose_context(cmsg.ctype, cmsg.content, isgroup=cmsg.is_group, msg=cmsg,no_need_at= not reply_at)
        if context:
            self.produce(context)
        else:
            logger.debug("本次context返回为空，不放入队列")
    def upload_pic(self,local_file,upload_url):
        '''
        '{"url":"https://openai-75050.gzc.vod.tencent-cloud.com/openaiassets_14eb211d797ccdf33edc19839a7bcbcc_2579861717036942746.jpg","filekey":"openaiassets_14eb211d797ccdf33edc19839a7bcbcc_2579861717036942746.jpg"}'
        :param local_file:
        :param upload_url:
        :return:
        '''
        if os.path.exists(local_file):
            upload_url = "https://openai.weixin.qq.com/weixinh5/webapp/h774yvzC2xlB4bIgGfX2stc4kvC85J/cos/upload"
            payload = {}
            files = [
                    ('media', (
                    '0bbe70c70de11d13ffb2c.jpg', open(local_file, 'rb'),
                    'image/jpeg'))
                    ]
            headers={
            'Cookie':'oin:sess=eyJ1aWQiOiJmT1FMdFd1bUc0UyIsInNpZ25ldGltZSI6MTcxNjk2NjAwNTUxMCwiX2V4cGlyZSI6MTcxNzA1MjQwNjI4NiwiX21heEFnZSI6ODY0MDAwMDB9;oin:sess.sig=rHMmxTzNuo3bYpAwWzSoMA3S4DQ;wxuin=16966005491375;wxuin.sig=DMJDEtL7jcUjxUMAcDjetb9HBrA'
            }

            response=requests.post(upload_url,headers = headers,data = payload,files = files)

            print(response.text)
            return response.json()
        else:
            logger.info(f"本地文件不存在")
            return ""


    # 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息
    def send(self, reply: Reply, context: Context):
        def send_long_text(bot, context: Context, reply):
            # 修改回复的方法，根据reply.ext字段判断回复方式
            # 1 真艾特回复 2 假艾特回复 3 不艾特回复
            # 4 引用回复不艾特 5 引用回复假艾特 6 引用回复真艾特 无法实现
            max_length = 1000
            cmsg: ChatMessage = context['msg']
            refer_name = cmsg.from_user_nickname
            receiver = context["receiver"]
            from_user_id = context["msg"].from_user_id
            if reply.type == ReplyType.TEXT  or reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
                content = reply.content
                if len(content)>max_length:
                    segments = content.split('\n')
                    current_message = ""
                    for segment in segments:
                        total_length = len(current_message) + len(segment) + 1
                        if total_length <= max_length:  # +1 for the newline character
                            if current_message:
                                current_message += '\n' + segment
                            else:
                                current_message = segment
                        else:
                            # bot.send_message(to_id=receiver, text=current_message)
                            if reply.ext == 1:  # @回复
                                if "@" not in current_message:
                                    current_message = "@" + refer_name + "\n" + current_message
                                bot.send_at_message(to_id=receiver, at_ids=from_user_id, content=current_message)
                            elif reply.ext == 2:  # 假艾特回复
                                if "@" not in current_message:
                                    current_message = "@" + refer_name + "\n" + current_message
                                bot.send_message(to_id=receiver, text=current_message)
                            elif reply.ext == 3:  # 不艾特回复
                                bot.send_message(to_id=receiver, text=current_message)
                            elif reply.ext == 4:  # 引用回复不艾特
                                cmsg: ChatMessage = context['msg']
                                refer_id = cmsg.from_user_id
                                uuid = cmsg._rawmsg.get("uuid")
                                refer_name = cmsg.from_user_nickname
                                bot.send_refer_msg(receiver, uuid, refer_id, refer_name, current_message)
                            elif reply.ext == 5 or reply.ext == 6:  # 引用回复艾特
                                if "@" not in current_message:
                                    current_message = "@" + refer_name + "\n" + current_message
                                cmsg: ChatMessage = context['msg']
                                refer_id = cmsg.from_user_id
                                uuid = cmsg._rawmsg.get("uuid")
                                refer_name = cmsg.from_user_nickname
                                bot.send_refer_msg(receiver, uuid, refer_id, refer_name, current_message)
                            else:
                                bot.send_message(to_id=receiver, text=current_message)
                            logger.info("[WX] sendMsg={}, receiver={}".format(current_message, receiver))
                            current_message = segment
                            time.sleep(2.0)

                else:
                    current_message = content
                if current_message or (current_message== "" and (reply.ext == 1 or reply.ext == 2)):
                    #bot.send_message(to_id=receiver, text=current_message)
                    if reply.ext == 1:  # @回复
                        if "@" not in current_message:
                            current_message = "@" + refer_name + "\n" + current_message
                        bot.send_at_message(to_id=receiver, at_ids=from_user_id, content=current_message)
                    elif reply.ext == 2:  # 假艾特回复
                        if "@" not in current_message:
                            current_message = "@" + refer_name + "\n" + current_message
                        bot.send_message(to_id=receiver, text=current_message)
                    elif reply.ext == 3:  # 不艾特回复
                        bot.send_message(to_id=receiver, text=current_message)
                    elif reply.ext == 4 :  # 引用回复不艾特
                        cmsg: ChatMessage = context['msg']
                        refer_id = cmsg.from_user_id
                        uuid = cmsg._rawmsg.get("uuid")
                        refer_name = cmsg.from_user_nickname
                        bot.send_refer_msg(receiver, uuid, refer_id, refer_name, current_message)
                    elif reply.ext == 5 or reply.ext == 6:  # 引用回复艾特
                        if "@" not in current_message:
                            current_message = "@" + refer_name + "\n" + current_message
                        cmsg: ChatMessage = context['msg']
                        refer_id = cmsg.from_user_id
                        uuid = cmsg._rawmsg.get("uuid")
                        refer_name = cmsg.from_user_nickname
                        bot.send_refer_msg(receiver, uuid, refer_id, refer_name, current_message)
                    else:
                        bot.send_message(to_id=receiver, text=current_message)
                    logger.info("[WX] sendMsg={}, receiver={}".format(current_message, receiver))
                    time.sleep(2.0)
        receiver = context["receiver"]
        if reply.type == ReplyType.TEXT:
            #修改回复的方法，根据reply.ext字段判断回复方式reply.type== ReplyType.ERRORorreply.type==
            # 1 真艾特回复 2 假艾特回复 3 不艾特回复
            # 4 引用回复不艾特 5 引用回复假艾特 6 引用回复真艾特 无法实现

            send_long_text(self.bot,context,reply)

            #self.bot.send_message(to_id=receiver,text=reply.content)
            #logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver))
        elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
            #self.bot.send_message(to_id=receiver,text=reply.content)
            send_long_text(self.bot, context, reply)

            logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver))
        elif reply.type == ReplyType.VOICE:
            #itchat.send_file(reply.content, toUserName=receiver)
            logger.info("[WX] sendFile={}, receiver={}".format(reply.content, receiver))
        elif reply.type == ReplyType.IMAGE_URL:  # 从网络下载图片
            #todo 这个地方，先发一段文字，然后再发图片
            img_url = reply.content
            if reply.ext: #如果有ext 说明有文字要发送，一次发完，这个地方已经完成了ext信息的包装

                self.bot.send_message(to_id=receiver,text=reply.ext["prompt"])
                #time.sleep(1.5)


            self.bot.send_image_url(to_id=receiver,url=reply.content)
            logger.info("[WX] sendImage url={}, receiver={}".format(img_url, receiver))
            #time.sleep(2)
            if reply.ext:
                for url in reply.ext["urls"]:
                    #time.sleep(2)
                    self.bot.send_image_url(to_id=receiver, url=url)
                    logger.info("[WX] sendImage url={}, receiver={}".format(url, receiver))

        elif reply.type == ReplyType.IMAGE:  # 从文件读取图片
            image_storage = reply.content
            #image_storage.seek(0)
            #itchat.send_image(image_storage, toUserName=receiver)
            logger.info("[WX] sendImage, receiver={}".format(receiver))
            # done 上传文件
            image_url = self.bot.upload_pic(image_storage, "")['url']
            self.bot.send_pic_msg(to_id=receiver, url=image_url)
            #self.bot.send_image_url(to_id=receiver, url=reply.content)
        elif reply.type == ReplyType.IMAGE_XML:  # 从文件读取图片
            image_xml = reply.content
            logger.info("[WX] forward image, receiver={}".format(receiver))

            self.bot.forward_img(to_id=receiver, xml=image_xml)
            #self.bot.send_image_url(to_id=receiver, url=reply.content)
        elif reply.type == ReplyType.FILE:  # 新增文件回复类型
            #todo
            file_storage = reply.content
            #itchat.send_file(file_storage, toUserName=receiver)
            logger.info("[WX] sendFile, receiver={}".format(receiver))
        elif reply.type == ReplyType.FILE_XML:  # 新增文件回复类型
            #todo
            file_storage = reply.content
            #self.bot.forward_file(file_storage, toUserName=receiver)
            logger.info("[WX] todo sendFile, receiver={}".format(receiver))
        elif reply.type == ReplyType.VIDEO:  # 新增视频回复类型
            #todo
            video_storage = reply.content
            #itchat.send_video(video_storage, toUserName=receiver)
            logger.info("[WX] sendFile, receiver={}".format(receiver))
        elif reply.type == ReplyType.VIDEO_URL:  # 新增视频URL回复类型
            # todo
            video_url = reply.content
            logger.debug(f"[WX] start download video, video_url={video_url}")
            video_res = requests.get(video_url, stream=True)
            video_storage = io.BytesIO()
            size = 0
            for block in video_res.iter_content(1024):
                size += len(block)
                video_storage.write(block)
            logger.info(f"[WX] download video success, size={size}, video_url={video_url}")
            video_storage.seek(0)
            #itchat.send_video(video_storage, toUserName=receiver)
            logger.info("[WX] sendVideo url={}, receiver={}".format(video_url, receiver))
        elif reply.type == ReplyType.LINK:
            self.bot.forward_video(receiver, reply.content)
            logger.info("[WX] sendCARD={}, receiver={}".format(reply.content, receiver))
        elif reply.type == ReplyType.InviteRoom:
            member_list = receiver
            room_id = reply.content
            if room_id in self.bot.shared_wx_contact_list:
                memberCount = self.bot.shared_wx_contact_list[room_id]['memberCount']
                if memberCount.isdigit() and int(memberCount) < 40:
                    self.bot.invite_room_direct(room_id, member_list)
                    logger.info("[WX] less than 40 sendInviteRoom={}, receiver={}".format(reply.content, receiver))
                else:
                    self.bot.invite_room_link(room_id, member_list)
                    logger.info("[WX] more then 40 sendInviteRoom={}, receiver={}".format(reply.content, receiver))
                if reply.ext:
                    time.sleep(2)
                    self.bot.send_message(to_id=receiver, text=reply.ext["prompt"])

            else:
                logger.error(f"[WX] room_id={room_id} not in shared_wx_contact_list")
        # 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息

#ch = WechatChannel()
class WechatPadChannel:
    # 类常量
    FAILED_MSG = '{"success": false}'
    SUCCESS_MSG = '{"success": true}'
    MESSAGE_RECEIVE_TYPE = "8001"

    def GET(self):
        return "Wechat iPad service start success!"

    # def POST(self):
    #     '''
    #     todo 校验发过来的token和auth
    #     '''
    #     try:
    #         msg = json.loads(web.data().decode("utf-8"))
    #         logger.debug(f"[Wechat] receive request: {msg}")
    #     except Exception as e:
    #         logger.error(e)
    #         return self.FAILED_MSG
    #     try:
    #         cmsg = WechatMessage(msg, True)
    #     except NotImplementedError as e:
    #         logger.debug("[WX]group message {} skipped: {}".format(msg["msg_id"], e))
    #         return None
    #     if msg['group']:
    #         WechatChannel().handle_group(cmsg)
    #     else:
    #         WechatChannel().handle_single(cmsg)
    #     return None

async def message_handler(recv, channel):
    channel.handle_group(recv)
    #await asyncio.create_task(channel.handle_group(recv))


# def callback(worker):
#     worker_exception = worker.exception()
#     if worker_exception:
#         logger.error(worker_exception)

#
# wechat_pad_channel = WechatPadChannel()
# @app.route('/chat', methods=['GET', 'POST'])
# def chat():
#     return wechat_pad_channel.handle_request()