import re

from bridge.context import ContextType
from channel.chat_message import ChatMessage
from common.log import logger
from common.tmp_dir import TmpDir
import json
import os
import xml.etree.ElementTree as ET



#from lib import itchat
#from lib.itchat.content import *

from channel.wechat.iPadWx import iPadWx
class WechatMessage(ChatMessage):
    '''

    '''

    def __init__(self, itchat_msg, is_group=False):
        super().__init__(itchat_msg)
        self.Appid = itchat_msg.get("Appid","")
        if self.Appid:
            return
        self.msg_id = itchat_msg["msg_id"]
        self.create_time = itchat_msg["arr_at"]
        self.is_group = itchat_msg["group"]
        self.room_id = itchat_msg["room_id"]
        self.bot = iPadWx()
        msg_type = itchat_msg["type"]
        if msg_type in ['8001','9001']   :
            self.ctype = ContextType.TEXT
            self.content = itchat_msg["msg"]
        elif msg_type   in ['8002','9002']:#群聊图片
            self.ctype = ContextType.IMAGE
            self.content = itchat_msg['msg']
            #self.bot.forward_img("gh_c95e05e75405", self.content)
            #self.content = TmpDir().path() + itchat_msg.get("FileName")  # content直接存临时目录路径
            #self._prepare_fn = lambda: itchat_msg.download(self.content)
        elif msg_type in ['8003', '9003']:
            self.ctype = ContextType.VIDEO
            self.content = itchat_msg['msg']
            #self.bot.forward_video("gh_c95e05e75405", self.content)
        elif msg_type  in ['8004','9004'] :#群聊语音消息
            self.ctype = ContextType.VOICE
            self.content = itchat_msg["msg"]
            #self.content = TmpDir().path() + itchat_msg.get("FileName")  # content直接存临时目录路径
            #self._prepare_fn = lambda: itchat_msg.download(self.content)
        # elif msg_type in ['8005']:#群聊红包、文件、链接、小程序等类型
        #     self.ctype = ContextType.XML
        #     self.content = itchat_msg["msg"]
        elif msg_type in ['8006', '9006']:  # 群聊地图位置消息
            self.ctype = ContextType.MAP
            self.content = itchat_msg["msg"]
        elif msg_type in ['8007', '9007']:#群聊表情包
            self.ctype = ContextType.EMOJI
            self.content = itchat_msg["msg"]
        elif msg_type in ['8008', '9008']:#群聊名片
            self.ctype = ContextType.CARD
            self.content = itchat_msg["msg"]
        elif msg_type in ['7005','9005','8005']: #xml格式的
            result = self.parse_wechat_message(itchat_msg["msg"])
            if result['message_type'] == 'sysmsgtemplate' and result['subtype'] == 'invite':
                self.ctype = ContextType.JOIN_GROUP
                self.content = itchat_msg["msg"]
                
                if result.get('joiners_usernames'):
                    if result.get('join_type') == 'qrcode':
                        # 扫码进群
                        joiner = result['joiners_usernames'][0]
                        sharer = result.get('sharer', {})
                        self.actual_user_nickname = joiner['nickname']
                        self.content = f"{joiner['nickname']} 通过扫描 {sharer.get('nickname', '未知用户')} 的二维码加入群聊"
                    else:
                        # 邀请进群
                        self.actual_user_nickname = result['joiners_usernames'][0]['nickname']
                        inviter = result.get('inviter_username', {})
                        self.content = f"{inviter.get('nickname', '未知用户')} 邀请 {self.actual_user_nickname} 加入群聊"
                else:
                    # 处理异常情况
                    logger.warning("No joiner information found in the message")
                    self.actual_user_nickname = "未知用户"
                    self.content = "新成员加入群聊"
                if msg_type =='9005': #XML消息类型变成了9005
                    self.ctype = ContextType.XML
                    self.content = itchat_msg.get("msg")
                    if result['message_type'] == 74:
                        self.ctype = ContextType.FILE

            elif result['message_type'] == 'pat':

                self.ctype = ContextType.PATPAT

                self.content = itchat_msg["msg"]

                if is_group:
                    self.from_user_id = result['from_user_id']
                    self.actual_user_id = result['from_user_id']
                    displayName, nickname = self.get_chatroom_nickname(self.room_id, self.actual_user_id)
                    self.actual_user_nickname = displayName or nickname
                    self.content = result['action']
            elif result['message_type'] == 'appmsg' and result['subtype'] == 'reference':
                # 这里只能得到nickname， actual_user_id还是机器人的id
                '''
                {
                'subtype': 'reference',
                'title': title,
                'reference': {
                    'type': refer_type,
                    'svrid': svrid,
                    'fromusr': fromusr,
                    'chatusr': chatusr,
                    'displayname': displayname,
                    'content': content.strip()
                    }
                }
                '''
                if result["reference"]["url"] and result["reference"]["url"] != "N/A":
                    self.ctype = ContextType.TEXT
                    # self.content = result["title"] #引用说的话
                    self.content = f'{result["title"]} {result["reference"]["url"]}'
                else:
                    self.ctype = ContextType.XML
                    # self.content = result["title"] #引用说的话
                    self.content = itchat_msg["msg"]

            elif result['message_type'] == 19 and 'title' in result and result['title'] == '群聊的聊天记录':

                # 这里只能得到nickname， actual_user_id还是机器人的id
                self.ctype = ContextType.LINK
                self.content = json.dumps(result["image_infos"])  # 内容 list
            elif result['message_type'] == 2000 and result['title'] == "微信转账":
                '''
                message_info = {
                    'title': title,
                    'message_type': message_type,
                    'feedesc': feedesc,
                    'pay_memo': pay_memo,
                    "receiver_username":receiver_username
                }
                '''
                self.ctype = ContextType.WCPAY

                self.content = result['feedesc'] + "\n" + result['pay_memo'] + "\n" + result[
                    'receiver_username'] + "\n" + str(result["paysubtype"])
                pass
            elif result['message_type'] == 6 or result['message_type'] == 74:
                self.ctype = ContextType.FILE
                self.content = itchat_msg["msg"]
            elif "你已添加了" in itchat_msg["msg"]:  # 通过好友请求
                self.ctype = ContextType.ACCEPT_FRIEND
                self.content = itchat_msg["msg"]

            elif is_group and ("移出了群聊" in itchat_msg["msg"]):
                self.ctype = ContextType.EXIT_GROUP
                self.content = itchat_msg["msg"]
                self.actual_user_nickname = re.findall(r"\"(.*?)\"", itchat_msg["msg"])

            elif "你已添加了" in itchat_msg["msg"]:  # 通过好友请求
                self.ctype = ContextType.ACCEPT_FRIEND
                self.content = itchat_msg["msg"]
            elif result['message_type']=="revokemsg":
                self.ctype = ContextType.REVOKE_MESSAGE
                self.content = itchat_msg["msg"]

            else:
                self.ctype = ContextType.XML
                self.content = itchat_msg["msg"]

                logger.error("Unsupported note message: ")

        elif msg_type in ['7001']: #添加好友消息
            # 解析 XML
            xml_data = itchat_msg["msg"]
            root = ET.fromstring(xml_data)

            # 获取 scene 和 ticket
            scene = root.get('scene')
            ticket = root.get('ticket')
            self.ctype = ContextType.ADD_FRIEND
            logger.info(f"scene: {scene}, ticket: {ticket}")
            self.content = xml_data

        # elif msg_type in ['8005','9005']:
        #     self.ctype = ContextType.FILE
        #     #self.content = TmpDir().path() + itchat_msg.get("FileName")  # content直接存临时目录路径
        #     if self.content:
        #         pass
                #self._prepare_fn = lambda: itchat_msg.download(self.content)
        elif msg_type == '9006':
            self.ctype = ContextType.XML
            self.content = itchat_msg.get("msg")

        else:
            pass
            #raise NotImplementedError("Unsupported message type: Type:{} MsgType:{}".format(msg_type,
            #                                                                                msg_type))
        if not self.from_user_id:
            self.from_user_id = itchat_msg["from_id"]

        self.to_user_id = itchat_msg["to_id"]

        # 虽然from_user_id和to_user_id用的少，但是为了保持一致性，还是要填充一下
        # 以下很繁琐，一句话总结：能填的都填了。
        #other_user_id: 对方的id，如果你是发送者，那这个就是接收者id，如果你是接收者，那这个就是发送者id，如果是群消息，那这一直是群id(必填)

        try:  # 陌生人时候, User字段可能不存在
            # my_msg 为True是表示是自己发送的消息
            self.my_msg = itchat_msg["bot_id"] == itchat_msg["from_id"]
            if self.is_group:
                self.other_user_id = itchat_msg["room_id"]
                displayName,nickname = self.get_chatroom_nickname(self.room_id, self.from_user_id)

                self.from_user_nickname = displayName or nickname
                self.self_display_name =  displayName or nickname
                _,self.to_user_nickname  = self.get_chatroom_nickname(self.room_id, self.to_user_id)

                #self.to_user_nickname = self.get_chatroom_nickname(self.room_id, self.to_user_id)
                self.other_user_nickname = iPadWx.shared_wx_contact_list[self.room_id]['nickName']
            else:
                if self.from_user_id not in iPadWx.shared_wx_contact_list:
                    self.save_single_contact(self.from_user_id)
                if self.from_user_id in iPadWx.shared_wx_contact_list:
                    self.from_user_nickname =  iPadWx.shared_wx_contact_list[self.from_user_id]['nickName']
                if itchat_msg['bot_id']==itchat_msg['from_id']:#机器人发送
                    self.other_user_id = itchat_msg["to_id"]
                    self.other_user_nickname = self.to_user_nickname
                else:
                    self.other_user_id = itchat_msg["from_id"]
                    self.other_user_nickname = self.from_user_nickname
            if itchat_msg["from_id"]:
                pass
                # 自身的展示名，当设置了群昵称时，该字段表示群昵称
                #self.self_display_name = self.from_user_nickname
        except KeyError as e:  # 处理偶尔没有对方信息的情况
            logger.warn("[WX]get other_user_id failed: " + str(e))

        if self.is_group:
            self.is_at = False if len(itchat_msg["at_ids"])==0 else True
            self.at_list = itchat_msg["at_ids"]
            #self.at_list_member = self.bot.shared_wx_contact_list[self.room_id]['chatRoomMembers']
            if not self.actual_user_id:
                self.actual_user_id = itchat_msg["from_id"]
            if self.ctype not in [ContextType.JOIN_GROUP, ContextType.PATPAT, ContextType.EXIT_GROUP]:
                pass
                self.actual_user_nickname = self.self_display_name #发送者的群昵称 还是本身的昵称
            subtract_res = self.content
            if self.is_at:

                subtract_res =self.remove_at_mentions(self.content)
                self.content=subtract_res
                logger.info(f"存在at 去除后{self.content}")
            for at_id in self.at_list:
                at_info = self.get_user(iPadWx.shared_wx_contact_list[self.room_id]["chatRoomMembers"],at_id)
                if at_info:
                    nickname = at_info['nickName']
                    if nickname:
                        pattern = f"@{re.escape(nickname)}(\u2005|\u0020)"
                        subtract_res = re.sub(pattern, r"", subtract_res)
                    displayName = at_info['displayName'] if at_info['displayName'] else ""
                    if displayName:
                        pattern = f"@{re.escape(at_info['displayName'])}(\u2005|\u0020)"
                        subtract_res = re.sub(pattern, r"", subtract_res)
                    # 如果昵称没去掉，则用替换的方法
                    if subtract_res == self.content :
                        # 前缀移除后没有变化，使用群昵称再次移除
                        # pattern = f"@{re.escape(context['msg'].self_display_name)}(\u2005|\u0020)"
                        if displayName:
                            subtract_res = self.content.replace("@" + displayName, "").replace(
                                "@" + displayName, "")
            if self.is_at:
                #subtract_res = self.remove_at_mentions(self.content)
                self.content = subtract_res
                logger.info(f"存在at2 去除后{self.content}")


    def remove_at_mentions(self,text):
        # 使用正则表达式匹配所有 @昵称 格式的片段
        cleaned_text = re.sub(r'@.*?\u2005', '', text)
        # 清理多余的空格和标点符号
        return cleaned_text.strip()
    def get_user(self,users, username):
        # 使用 filter 函数通过给定的 userName 来找寻符合条件的元素
        if not isinstance(users,list):
            return None
        #res = list(filter(lambda user: user['userName'] == username, users))
        result=None
        for item in users:
            if item["userName"]==username:
                result=item
                break
        return result
        return res[0] if res else None  # 如果找到了就返回找到的元素（因为 filter 返回的是列表，所以我们取第一个元素），否则返回 None
    def get_chatroom_nickname(self, room_id: str = 'null', wxid: str = 'ROOT'):
        '''
        获取群聊中用户昵称 Get chatroom's user's nickname
        群成员如果变了，没有获取到，则重新获取
        :param room_id: 群号(以@chatroom结尾) groupchatid(end with@chatroom)
        :param wxid: wxid(新用户的wxid以wxid_开头 老用户他们可能修改过 现在改不了) wechatid(start with wxid_)
        :return: Dictionary
        '''
        if room_id.endswith("@chatroom") and not wxid.endswith("@chatroom"):
            if room_id in iPadWx.shared_wx_contact_list :
                logger.debug("无需网络获取，本地读取")
                #logger.info(iPadWx.shared_wx_contact_list[room_id])
                member = iPadWx.shared_wx_contact_list[room_id]['chatRoomMembers']
                #logger.info(member)
                member_info = self.get_user(member, wxid)

            else:
                #本地不存在群信息，网络获取
                room_info = self.bot.get_room_info(room_id)
                iPadWx.shared_wx_contact_list[room_id] = room_info['data']
                members = self.bot.get_chatroom_memberlist(room_id)
                member_info = self.get_user(members['data'], wxid)
                iPadWx.shared_wx_contact_list[room_id]['chatRoomMembers'] =members['data']
                self.save_contact()
            #本地群存在，但是成员没找到，需要网络获取
            if not member_info:
                members = self.bot.get_chatroom_memberlist(room_id)
                member_info = self.get_user(members['data'], wxid)
                iPadWx.shared_wx_contact_list[room_id]['chatRoomMembers'] = members['data']
                self.save_contact()
            if member_info:
                return  member_info['displayName'] , member_info['nickName']
        return None,None

    def parse_wechat_message(self, xml_data):
        def get_member_info(member_element):
            if member_element is not None:
                username = member_element.findtext('.//username').strip()
                nickname = member_element.findtext('.//nickname').strip()
                return {
                    'username': username,
                    'nickname': nickname
                }
            else:
                return None

        # 解析XML
        root = ET.fromstring(xml_data)

        # 获取消息类型
        message_type = root.get('type')
        refermsg = root.find('.//refermsg')
        # 根据消息类型提取信息
        if message_type == 'pat':
            # 拍一拍消息
            from_username = root.find('.//fromusername').text if root.find('.//fromusername') is not None else None
            template_content = root.find('.//template').text if root.find('.//template') is not None else None
            return {
                'message_type': message_type,
                'from_user_id': from_username,
                'action': template_content
            }
        elif message_type == 'sysmsgtemplate':
            # 系统消息，可能是邀请或撤回
            content_template = root.find('.//sysmsgtemplate/content_template')
            if content_template is not None and content_template.get('type') in ['tmpl_type_profile',"tmpl_type_profilewithrevoke"]:
                template_text = content_template.find('.//template').text if content_template.find('.//template') is not None else ''
                
                # 处理扫码进群的情况
                if '"通过扫描"' in template_text and '分享的二维码加入群聊' in template_text:
                    # 获取加入群聊的成员信息
                    adder_link = root.find('.//link_list/link[@name="adder"]')
                    from_link = root.find('.//link_list/link[@name="from"]')
                    
                    joiners = []
                    if adder_link is not None:
                        member = adder_link.find('.//member')
                        if member is not None:
                            username = member.findtext('username', '').strip()
                            nickname = member.findtext('nickname', '').strip()
                            joiners.append({
                                'username': username,
                                'nickname': nickname
                            })
                    
                    # 获取分享二维码的人信息
                    sharer = None
                    if from_link is not None:
                        member = from_link.find('.//member')
                        if member is not None:
                            username = member.findtext('username', '').strip()
                            nickname = member.findtext('nickname', '').strip()
                            sharer = {
                                'username': username,
                                'nickname': nickname
                            }
                    
                    return {
                        'message_type': 'sysmsgtemplate',
                        'subtype': 'invite',
                        'joiners_usernames': joiners,
                        'sharer': sharer,
                        'join_type': 'qrcode'
                    }
                
                # 处理其他邀请情况（原有逻辑）

                inviter_link = root.find('.//link_list/link[@name="username"]') or root.find('.//link_list/link[@name="names"]')
                if inviter_link is None:
                    inviter_link = root.find('.//link_list/link[@name="from"]')
                inviter = get_member_info(inviter_link.find('.//member') if inviter_link is not None else None)

                names_link = root.find('.//link_list/link[@name="names"]')
                if names_link is None:
                    names_link = root.find('.//link_list/link[@name="adder"]')
                members = names_link.findall('.//memberlist/member') if names_link is not None else []
                joiners = [get_member_info(member) for member in members if get_member_info(member)]
                
                return {
                    'message_type': 'sysmsgtemplate',
                    'subtype': 'invite',
                    'inviter_username': inviter,
                    'joiners_usernames': joiners,
                    'join_type': 'invite'
                }
            
        elif message_type == 'revokemsg':
            # 消息撤回
            session = root.find('./session').text if root.find('./session') is not None else None
            msgid = root.find('./revokemsg/msgid').text if root.find('./revokemsg/msgid') is not None else None
            newmsgid = root.find('./revokemsg/newmsgid').text if root.find('./revokemsg/newmsgid') is not None else None
            replacemsg = root.find('./revokemsg/replacemsg').text if root.find(
                './revokemsg/replacemsg') is not None else None

            # 返回撤回消息的字典
            return {
                'message_type': 'revokemsg',
                'session': session,
                'original_message_id': msgid,
                'new_message_id': newmsgid,
                'replace_message': replacemsg
            }
        elif message_type == 'NewXmlChatRoomAccessVerifyApplication':
            # 提取关键信息
            # 提取邀请人用户名
            inviter_username = root.find('.//inviterusername').text if root.find(
                './/inviterusername') is not None else "N/A"

            # 从 <text> 标签中提取邀请人的昵称
            text_content = root.find('.//text').text if root.find('.//text') is not None else ""
            start_index = text_content.find('"') + 1
            end_index = text_content.find('"', start_index + 1)
            inviter_nickname = text_content[start_index:end_index] if start_index < end_index else "N/A"

            room_name = root.find('.//RoomName').text if root.find('.//RoomName') is not None else "N/A"
            invitation_reason = root.find('.//invitationreason').text if root.find(
                './/invitationreason') is not None else "N/A"

            joiners = []
            memberlist = root.find('.//memberlist')
            if memberlist is not None:
                for member in memberlist.findall('member'):
                    username = member.find('username').text if member.find('username') is not None else "N/A"
                    nickname = member.find('nickname').text if member.find('nickname') is not None else "N/A"
                    headimgurl = member.find('headimgurl').text if member.find('headimgurl') is not None else "N/A"
                    joiners.append({
                        'username': username,
                        'nickname': nickname,
                        'headimgurl': headimgurl
                    })

                # 构建JSON结构
            message_info = {
                'message_type': 'NewXmlChatRoomAccessVerifyApplication',
                'subtype': 'invite',
                'inviter_username': inviter_username,
                'inviter_nickname': inviter_nickname,
                'room_name': room_name,
                'invitation_reason': invitation_reason,
                'joiners': joiners
            }

            return message_info

        elif refermsg is not None:
            # 这是一个引用消息
            logger.info("引用消息存在，提取关键信息：")

            appmsg = root.find('appmsg')
            title = appmsg.find('title').text if appmsg.find('title') is not None else "N/A"


            svrid = refermsg.find('svrid').text if refermsg.find('svrid') is not None else "N/A"
            fromusr = refermsg.find('fromusr').text if refermsg.find('fromusr') is not None else "N/A"
            chatusr = refermsg.find('chatusr').text if refermsg.find('chatusr') is not None else "N/A"
            displayname = refermsg.find('displayname').text if refermsg.find('displayname') is not None else "N/A"
            content = refermsg.find('content').text if refermsg.find('content') is not None else "N/A"
            refer_type = refermsg.find('type').text if refermsg.find('type') is not None else "N/A"
            try:
                root2 = ET.fromstring(content)
                url = root2.find('.//url').text if root2.find('.//url') is not None else "N/A"
                #refer_type = refermsg.find('type').text if refermsg.find('type') is not None else "N/A"
            except:
                url = ""
                #refer_type=None
            message_info = {
                'message_type': 'appmsg',
                'title': title,
                'content': content
            }
            # 添加引用消息的信息
            message_info.update({
                'subtype': 'reference',
                'title': title,
                'reference': {
                    'type': refer_type,
                    'svrid': svrid,
                    'fromusr': fromusr,
                    'chatusr': chatusr,
                    'displayname': displayname,
                    'content': content,
                    'url': url,
                }
            })
            # 输出提取的信息
            logger.info(f"消息内容: {title}")
            logger.info(f"引用消息类型: {refer_type}")
            logger.info(f"消息ID: {svrid}")
            logger.info(f"发送人: {fromusr}")
            logger.info(f"聊天群: {chatusr}")
            logger.info(f"显示名: {displayname}")
            logger.info(f"引用消息: {content}")
            logger.info(f"文章URl: {url}")
            return message_info
        else:
            # 提取关键信息
            title = root.find('.//title').text if root.find('.//title') is not None else ''
            message_type = root.find('.//type').text if root.find('.//type') is not None else ''
            if message_type.isdigit():
                message_type = int(message_type)
            if title =='群聊的聊天记录' and message_type ==19:
                from_username = root.find('.//fromusername').text if root.find('.//fromusername') is not None else ''
                # 提取图片信息
                images_info = []
                recorditem = root.findall(".//recorditem")
                # 遍历datalist中的所有dataitem元素
                root2 = ET.fromstring(recorditem[0].text)
                for dataitem in root2.findall('.//datalist/dataitem'):
                    # 提取dataitem中的信息
                    image_info = {
                        # 'htmlid': dataitem.get('htmlid'),
                        'datatype': dataitem.get('datatype'),
                        # 'dataid': dataitem.get('dataid'),
                        # 'messageuuid': dataitem.find('.//messageuuid').text if dataitem.find('.//messageuuid') is not None else '',
                        # 'cdnthumburl': dataitem.find('.//cdnthumburl').text if dataitem.find('.//cdnthumburl') is not None else '',
                        'sourcetime': dataitem.find('.//sourcetime').text if dataitem.find(
                            './/sourcetime') is not None else '',
                        # 'fromnewmsgid': dataitem.find('.//fromnewmsgid').text if dataitem.find('.//fromnewmsgid') is not None else '',
                        # 'datasize': dataitem.find('.//datasize').text if dataitem.find('.//datasize') is not None else '',
                        # 'thumbfullmd5': dataitem.find('.//thumbfullmd5').text if dataitem.find('.//thumbfullmd5') is not None else '',
                        'filetype': dataitem.find('.//filetype').text if dataitem.find(
                            './/filetype') is not None else '',
                        # 'cdnthumbkey': dataitem.find('.//cdnthumbkey').text if dataitem.find('.//cdnthumbkey') is not None else '',
                        'sourcename': dataitem.find('.//sourcename').text if dataitem.find(
                            './/sourcename') is not None else '',
                        'datadesc': dataitem.find('.//datadesc').text if dataitem.find(
                            './/datadesc') is not None else '',
                        # 'cdndataurl': dataitem.find('.//cdndataurl').text if dataitem.find('.//cdndataurl') is not None else '',
                        # 'sourceheadurl': dataitem.find('.//sourceheadurl').text if dataitem.find('.//sourceheadurl') is not None else '',
                        # 'fullmd5': dataitem.find('.//fullmd5').text if dataitem.find('.//fullmd5') is not None else ''
                    }
                    # 将提取的信息添加到images_info列表中
                    images_info.append(image_info)

                # 构建JSON结构
                message_info = {
                    'title': title,
                    'message_type': message_type,
                    'from_username': from_username,
                    'image_infos': images_info
                }

                # 将结果转换为JSON字符串
                json_result = json.dumps(message_info, ensure_ascii=False, indent=4)

                return  message_info
            if title == "微信转账" and message_type == 2000:
                # 提取feedesc中的转账金额
                feedesc = root.find(".//feedesc").text.replace("￥", "")

                # 提取pay_memo
                pay_memo = root.find(".//pay_memo").text
                paysubtype = root.find(".//paysubtype").text

                receiver_username = root.find(".//receiver_username").text
                # 构建JSON结构
                message_info = {
                    'title': title,
                    'message_type': message_type,
                    'feedesc': feedesc,
                    'pay_memo': pay_memo if pay_memo else '',
                    "receiver_username": receiver_username,
                    "paysubtype": paysubtype
                }
                return message_info
            elif message_type == 74 or message_type == 6: #文件类型
                message_info = {
                    'title': title,
                    'message_type': message_type,
                }
                return message_info
            return {'message_type': message_type, 'info': '未知消息类型'}

    def load_contact(self):
        if os.path.exists("contact.json"):
            iPadWx.shared_wx_contact_list = json.load(open("contact.json",'r',encoding='utf-8'))
            logger.info(f"读取联系人!")
            pass
    def save_contact(self):

        json.dump(iPadWx.shared_wx_contact_list,open("contact.json",'w',encoding='utf-8'), indent=4)
        logger.info(f"保存联系人!{iPadWx.shared_wx_contact_list}")

    def save_single_contact(self,user_id):
        result = self.bot.get_contact_info(user_id)
        # 将好友保存到联系人中
        if result.get('code') == 0 and result.get('data')[0]:
            logger.info(f"用户昵称不存在,重新获取用户信息")
            info = result.get('data', {})[0]
            nickname = info.get('nickName')
            fromusername = info.get('userName')
            alias = info.get('weixin')
            sex = info.get('sex')
            bigheadimgurl = info.get('bigHead')
            smallheadimgurl = info.get('smallHead')
            remark = info.get('remark')
            if fromusername not in iPadWx.shared_wx_contact_list:
                iPadWx.shared_wx_contact_list[fromusername] = {
                    'nickName': nickname,
                    'userName': fromusername,
                    'weixin': alias,
                    'sex': sex,
                    'bigHead': bigheadimgurl,
                    'smallHead': smallheadimgurl,
                    "remark":remark

                }
                self.bot.save_contact()