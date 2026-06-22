import requests, json, base64, time, struct, datetime, re
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from protobuf_decoder.protobuf_decoder import Parser
from typing import Dict, Any, Optional, Tuple, Union, TypedDict, List
from dataclasses import dataclass
from enum import IntEnum
import hashlib

class ProtoBuf:
 def __init__(self, data):
  self.data = data

 def varint(self, buffer: bytes, pos: int = 0) -> Tuple[int, int]:
  result, shift = 0, 0
  while shift < 64 and pos < len(buffer):
   byte = buffer[pos]
   pos += 1
   result |= (byte & 0x7F) << shift
   if not (byte & 0x80):
    return result, pos
   shift += 7
  return result, pos

 def repeated(self, data: bytes) -> List[int]:
  pos, out = 0, []
  while pos < len(data):
   val, pos = self.varint(data, pos)
   out.append(val)
  return out

 def string(self, buffer: bytes, pos: int) -> Tuple[str, int]:
  length, pos = self.varint(buffer, pos)
  newpos = min(pos + length, len(buffer))
  value = buffer[pos:newpos]
  try: value = value.decode("utf-8")
  except: pass
  return value, newpos

 def fixed32(self, buffer: bytes, pos: int) -> Tuple[int, int]:
  return (struct.unpack("<I", buffer[pos:pos + 4])[0], pos + 4) if pos + 4 <= len(buffer) else (0, pos)

 def fixed64(self, buffer: bytes, pos: int) -> Tuple[int, int]:
  return (struct.unpack("<Q", buffer[pos:pos + 8])[0], pos + 8) if pos + 8 <= len(buffer) else (0, pos)

 def parse_field(self, buffer: bytes, pos: int) -> Tuple[int, Any, int]:
  if pos >= len(buffer): return 0, None, pos
  key, pos = self.varint(buffer, pos)
  field_number, wire_type = key >> 3, key & 0x7
  try:
   if wire_type == 0: value, pos = self.varint(buffer, pos)
   elif wire_type == 1: value, pos = self.fixed64(buffer, pos)
   elif wire_type == 2: value, pos = self.string(buffer, pos)
   elif wire_type == 5: value, pos = self.fixed32(buffer, pos)
   else: return field_number, None, pos
  except (struct.error, IndexError):
   return field_number, None, pos
  return field_number, value, pos

 def protobuf(self, buffer: Optional[bytes] = None, offset: int = 0) -> Dict[str, Any]:
  if buffer is None:
   buffer = self.data
  result = {}
  while offset < len(buffer):
   field_number, value, offset = self.parse_field(buffer, offset)
   if isinstance(value, bytes) and value:
    try:
     nested = self.protobuf(value)
     if nested: value = nested
    except: pass
   key = str(field_number)
   result.setdefault(key, []).append(value)
  return {k: v[0] if len(v) == 1 else v for k, v in result.items()}

 def fieldsRaw(self, buf: bytes, pos: int) -> Tuple[int, int, bytes, int, int]:
  start = pos
  key, pos = self.varint(buf, pos)
  num, wt = key >> 3, key & 0x7
  if wt == 0: _, end = self.varint(buf, pos)
  elif wt == 1: end = pos + 8
  elif wt == 2:
   length, lp = self.varint(buf, pos)
   end = lp + length
  elif wt == 5: end = pos + 4
  else: return num, wt, b'', pos, pos
  return num, wt, buf[start:end], pos, end

 def EXTRACT_FIELDS(self, fields: List[int], mode: str = "repeated") -> List:
  cur = self.data
  for depth, target in enumerate(fields):
   pos = 0; found = False
   if depth == len(fields) - 1:
    results = []
    while pos < len(cur):
     num, wt, raw, val_start, val_end = self.fieldsRaw(cur, pos)
     if num == target:
      if mode == "repeated":
       if wt == 0:
        val, _ = self.varint(cur, val_start)
        results.append(val)
       elif wt == 2:
        _, lp = self.varint(cur, val_start)
        packed = cur[lp:val_end]
        results += self.repeated(packed)
      elif mode == "bytes":
       if wt == 2:
        _, lp = self.varint(cur, val_start)
        results.append(cur[lp:val_end])
       else:
        results.append(cur[val_start:val_end])
     pos = val_end
    if len(results) == 0: return []
    if len(results) == 1: return results[0]
    return results
   else:
    while pos < len(cur):
     num, wt, raw, val_start, val_end = self.fieldsRaw(cur, pos)
     if num == target and wt == 2:
      _, lp = self.varint(cur, val_start)
      cur = cur[lp:val_end]
      found = True; break
     pos = val_end
    if not found: return []
  return []


def Encrypt(value):
 value = int(value)
 result = []
 while value > 0x7F:
  result.append((value & 0x7F) | 0x80)
  value >>= 7
 result.append(value)
 return bytes(result)

def Decrypt(value):
 result, shift = 0, 0
 for byte in bytes.fromhex(value):
  result |= (byte & 0x7F) << shift
  if not (byte & 0x80):
   break
  shift += 7
 return result

def parse_results(parsed_results):
 result_dict = {}
 for result in parsed_results:
  if result.field not in result_dict:
   result_dict[result.field] = []
  field_data = {}
  if result.wire_type in ["varint", "string", "bytes"]:
   field_data = result.data
  elif result.wire_type == "length_delimited":
   field_data = parse_results(result.data.results)
  result_dict[result.field].append(field_data)
 return {
  key: value[0] if len(value) == 1
  else value for key, value in result_dict.items()
  }

protobuf_dec = lambda data: json.dumps(parse_results(
 Parser().parse(data)
 ), ensure_ascii=False)

def AES_CBC128(data, key, iv):
 cipher = AES.new(key, AES.MODE_CBC, iv)
 return cipher.encrypt(pad(data, 0x10))

def create_varint_field(field_number, value):
 field_header = (field_number << 3) | 0
 return Encrypt(field_header) + Encrypt(value)

def create_length_delimited_field(field_number, value):
 field_header = (field_number << 3) | 2
 encoded_value = value.encode() if isinstance(value, str) else value
 return Encrypt(field_header) + Encrypt(len(encoded_value)) + encoded_value

def pb_encode(fields):
 packet = bytearray()
 for field, value in fields.items():
  if isinstance(value, list):
   for item in value:
    if isinstance(item, dict):
     packet.extend(create_length_delimited_field(field, pb_encode(item)))
  elif isinstance(value, dict):
   nested_packet = pb_encode(value)
   packet.extend(create_length_delimited_field(field, nested_packet))
  elif isinstance(value, int):
   packet.extend(create_varint_field(field, value))
  elif isinstance(value, str) or isinstance(value, bytes):
   packet.extend(create_length_delimited_field(field, value))
 return bytes(packet)




class gayerr(Exception): pass
@dataclass
class account_data:
 access_token = ""
 open_id = ""
 platform = 0x4
 login_platform = 0x4
 main_active_platform = 0x4
 chat_ip = chat_port = online_ip = online_port  = ""
 create_time = None
 expiry_time = None
 guild_id = None
 guild_code = None
 login_token  = None
 account_id = None
 base_url = None
 login_time = None
 key = None
 iv = None


class gringay:
 @staticmethod
 def tokendecode(token):
  try:
   parts = token.split(".")
   if len(parts) != 3: raise gayerr("Invalid token format")
   payload = parts[1]
   payload += "=" * (0x4 - len(payload) % 0x4)
   return json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
  except (ValueError, json.JSONDecodeError) as e: pass
 
 @staticmethod
 def format_timestamp(timestamp):
  if timestamp is None: return ""
  return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp))

def storeApps(package):
 I=requests.get(f"https://play.google.com/store/apps/%s"%package)
 I=re.search(r'\[\[\["(\d+\.\d+\.\d+)"\]\]', I.text)
 if I:return I.group(1)
 return None

def bdversion(ver: str = None):
    import requests
    requests.packages.urllib3.disable_warnings()

    if not ver:
        ver = storeApps("details?id=com.dts.freefireth")

    try:
        url = "https://version.common.redflamenco.com/live/ver.php?version=%s&lang=vi&device=android&region=VN" % ver
        res = requests.get(url, verify=False, timeout=10)

        if res.status_code == 200:
            return res.json()
        else:
            print("API lỗi:", res.status_code)
            return None

    except Exception as e:
        print("bdversion lỗi:", e)
        return None
# Details: https://api.freefireservice.dnc.su/ff.status
# Telegram: @grider_modz

class APIClient:
 def __init__(self):
  self._data = account_data()
  detail_vers = bdversion()
  self.is_emulator = False
  self.language = "vn"
  self.base_url = detail_vers["server_url"]
  self.client_version = detail_vers["remote_version"]
  self.release_version = detail_vers["latest_release_version"]
  self.key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
  self.iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
  self.session = requests.Session()
  self.session.headers.update({
  "User-Agent": "UnityPlayer/2022.3.47f1(UnityWebRequest/1.0,libcurl/8.5.0- DEV)",  "X-GA": "v1 1", "Content-Type": "application/x-www-form-urlencoded",
  "Accept-Encoding": "deflate, gzip", "Accept": "*/*","X-Unity-Version": "2022.3.47f1",
  "Host": "loginbp.ggblueshark.com", "ReleaseVersion": self.release_version
  })

 def auth_guest_token(self, uid, password):
  payload = {
   "uid": str(uid), "password": str(password),
   "response_type": "token", "client_type": "2", "client_id": "100067", 
   "client_secret": bytes([50, 101, 101, 52, 52, 56, 49, 57, 101, 57, 98, 52, 53, 57, 56, 56, 52, 53, 49, 52, 49, 48, 54, 55, 98, 50, 56, 49, 54, 50, 49, 56, 55, 52, 100, 48, 100, 53, 100, 55, 97, 102, 57, 100, 56, 102, 55, 101, 48, 48, 99, 49, 101, 53, 52, 55, 49,53, 98, 55, 100, 49, 101, 51]).decode()
   }
  try:
   data = requests.post(
    "https://auth.garena.com/oauth/guest/token/grant",
    data=payload,
    headers={
     "Accept-Encoding": "gzip", "Accept-Encoding": "gzip, deflate",
     "Content-Type": "application/x-www-form-urlencoded",
     "User-Agent": "Mozilla/5.0 (Android 9; Mobile; rv:91.0) Gecko/91.0 Firefox/91.0",
     }
    ).json()
   if "access_token" not in data: return "account not found"
   self._data.access_token = data["access_token"]
   self._data.open_id = data["open_id"]
   self._data.platform = data.get("platform", 0x4)
   self._data.login_platform = data.get("login_platform", 0x4)
   self._data.main_active_platform = data.get("main_active_platform")
   self._data.create_time = data.get("create_time")
   self._data.expiry_time = data.get("expiry_time")
  except Exception as e: print(e)

 def auth_token_inspect(self, access_token):
  try:
   data = requests.get(
    "https://auth.garena.com/oauth/token/inspect",
    params={"token": access_token}
    ).json()
   if "open_id" not in data: raise gayerr("Invalid access token")
   self._data.access_token = access_token
   self._data.open_id = data["open_id"]
   self._data.platform = data.get("platform", 0x4)
   self._data.login_platform = data.get("login_platform", 0x4)
   self._data.main_active_platform = data.get("main_active_platform")
   self._data.create_time = data.get("create_time")
   self._data.expiry_time = data.get("expiry_time")
  except Exception as e: pass

 def MajorLogin(self):
  try:
   try:
      ip = requests.get('https://api.ipify.org', timeout=5).text
   except:
      ip = "113.167.116.36"

   fields = {}
   fields[3] = time.strftime("%Y-%m-%d %H:%M:%S")
   fields[4] = "free fire"
   fields[5] = 1
   fields[7] = self.client_version 
   fields[8] = "Android OS 12 / API-31 (SP1A.210812.016/V13.0.8.0.SJHCNXM)"
   fields[9] = "Handheld"
   fields[11] = "WIFI"
   fields[12] = 1666
   fields[13] = 750
   fields[14] = "440"
   fields[15] = "ARM64 FP ASIMD AES | 2600 | 8"
   fields[16] = 5479
   fields[17] = "Mali-G57 MC5"
   fields[18] = "OpenGL ES 3.2 v1.r32p1-00bet5.e94274a04d1e4e37d3804a00cb1f4074"
   fields[19] = "Google|21cd1993-491c-45f0-9aee-f4bf86b9245b"
   fields[20] = ip
   fields[21] = self.language
   fields[22] = str(self._data.open_id)
   fields[23] = "4"
   fields[24] = "Handheld"
   fields[25] = "Xiaomi M2004J7AC"
   fields[29] = str(self._data.access_token)
   fields[30] = 1
   fields[42] = "WIFI"
   fields[57] = "7428b253defc164018c604a1ebbfebdf"
   fields[60] = 48520
   fields[61] = 28119
   fields[62] = 4498
   fields[64] = 28263
   fields[65] = 48520
   fields[66] = 28263
   fields[67] = 48520
   fields[73] = 2
   fields[74] = "/data/app/~~iMOsnrV6G19kswoTGJGYgQ==/com.dts.freefireth-SFAA3QulcKsIN_SWyri7zA==/lib/arm64"
   fields[76] = 1
   fields[77] = "17e6a447803a17e4f59e3fd734efc5ae|/data/app/~~iMOsnrV6G19kswoTGJGYgQ==/com.dts.freefireth-SFAA3QulcKsIN_SWyri7zA==/base.apk"
   fields[78] = 3
   fields[79] = 2
   fields[81] = "64"
   fields[83] = "2019120270"
   fields[86] = "OpenGLES2"
   fields[87] = 255
   fields[88] = 4
   fields[90] = "Dia Chi"
   fields[91] = "22"
   fields[92] = 4275
   fields[93] = "android"
   fields[94] = "KqsHT2CnbP+CILeOnb+OUB8t2RSH3z76xfxPgY7My2napifnqTdAvVbbxUjA1J8kEj6yUng+sn/m+Bl6rX6Gv+tto7A="
   fields[95] = 111207
   fields[96] = '{"cur_rate":null,"support_etc2":false}'
   fields[97] = 1
   fields[98] = 1
   fields[99] = "4"
   fields[100] = "4"
   fields[102] = bytes.fromhex('4b074247540a0c0530')
   response = self.session.post(
    "%sMajorLogin" % self.base_url,
    data = AES_CBC128(
     pb_encode(fields),
     self.key, self.iv
    )
   )
   pb = ProtoBuf(response.content)
   res = pb.protobuf()
   self._data.account_id = res.get("1")
   self._data.server = res.get("3")
   self._data.login_token = res.get("8")
   self._data.base_url = res.get("10")
   self._data.login_time = res.get("21")
   self._data.key = pb.EXTRACT_FIELDS([22], mode="bytes")
   self._data.iv = pb.EXTRACT_FIELDS([23], mode="bytes")
  except Exception as e: pass

 def GetLoginData(self):
  try:
   try:
      ip = requests.get('https://api.ipify.org', timeout=5).text
   except:
      ip = "113.167.116.36"

   fields = {}
   fields[3] = time.strftime("%Y-%m-%d %H:%M:%S")
   fields[4] = "free fire"
   fields[5] = 1
   fields[7] = self.client_version 
   fields[8] = "Android OS 12 / API-31 (SP1A.210812.016/V13.0.8.0.SJHCNXM)"
   fields[9] = "Handheld"
   fields[11] = "WIFI"
   fields[12] = 1666
   fields[13] = 750
   fields[14] = "440"
   fields[15] = "ARM64 FP ASIMD AES | 2600 | 8"
   fields[16] = 5479
   fields[17] = "Mali-G57 MC5"
   fields[18] = "OpenGL ES 3.2 v1.r32p1-00bet5.e94274a04d1e4e37d3804a00cb1f4074"
   fields[19] = "Google|21cd1993-491c-45f0-9aee-f4bf86b9245b"
   fields[20] = ip
   fields[21] = self.language
   fields[22] = str(self._data.open_id)
   fields[23] = "4"
   fields[24] = "Handheld"
   fields[25] = "Xiaomi M2004J7AC"
   fields[29] = str(self._data.access_token)
   fields[30] = 1
   fields[42] = "WIFI"
   fields[57] = "7428b253defc164018c604a1ebbfebdf"
   fields[60] = 48520
   fields[61] = 28119
   fields[62] = 4498
   fields[64] = 28263
   fields[65] = 48520
   fields[66] = 28263
   fields[67] = 48520
   fields[73] = 2
   fields[74] = "/data/app/~~iMOsnrV6G19kswoTGJGYgQ==/com.dts.freefireth-SFAA3QulcKsIN_SWyri7zA==/lib/arm64"
   fields[76] = 1
   fields[77] = "17e6a447803a17e4f59e3fd734efc5ae|/data/app/~~iMOsnrV6G19kswoTGJGYgQ==/com.dts.freefireth-SFAA3QulcKsIN_SWyri7zA==/base.apk"
   fields[78] = 3
   fields[79] = 2
   fields[81] = "64"
   fields[83] = "2019120270"
   fields[86] = "OpenGLES2"
   fields[87] = 255
   fields[88] = 4
   fields[90] = "Dia Chi"
   fields[91] = "22"
   fields[92] = 4275
   fields[93] = "android"
   fields[94] = "KqsHT2CnbP+CILeOnb+OUB8t2RSH3z76xfxPgY7My2napifnqTdAvVbbxUjA1J8kEj6yUng+sn/m+Bl6rX6Gv+tto7A="
   fields[95] = 111207
   fields[96] = '{"cur_rate":null,"support_etc2":false}'
   fields[97] = 1
   fields[98] = 1
   fields[99] = "4"
   fields[100] = "4"
   fields[102] = bytes.fromhex('4b074247540a0c0530')
   response = self.session.post(
     "%s/GetLoginData" % self._data.base_url,
     headers = {
      "Authorization": "Bearer %s" % self._data.login_token,
      "Host": self._data.base_url[8:]
      }, data = AES_CBC128(
      pb_encode(fields),
      self.key, self.iv
     )
    )
   data = json.loads(protobuf_dec(response.content.hex()))
   self.logindata = data
   self._data.guild_id = data.get("20")
   self._data.guild_code = data.get("55")
   sv, chat = data.get("14"), data.get("32")
   if len(chat) > 6: self._data.chat_port, self._data.chat_ip = chat[-5:], chat[:-6]
   if len(sv) > 6: self._data.online_port, self._data.online_ip = sv[-5:], sv[:-6]
  except Exception as e: pass

 def TAO_PACKET_XT(self) -> str:
  try:
   esid = lambda rec: (
    lambda s: s[rec.upper()] if rec.upper() in s else None)(
     {x["2"].upper(): x["1"] for x in self.logindata["19"]}
    )
   eid = hex(self._data.account_id)[2:]
   bytestoken = self._data.login_token.encode()
   encrypts = AES_CBC128(bytestoken, self._data.key, self._data.iv).hex()
   lengths = hex(len(encrypts) // 2)[2:]
   header = ("0" * 16)[:max(0, 16 - len(eid))]
   packet = "%s%s%s%X%05d%s%s" % (
     "%02d%02X" % (1, esid(self._data.server)), header,
     eid, self._data.login_time, 0x0, lengths, encrypts
    )
   return bytes.fromhex(packet)
  except Exception as e: print(e)

 def auth(self, access_token, is_emulator = False):
  try:
   self.is_emulator = is_emulator
   if ":" in access_token:
    uid, password = access_token.split(":")
    self.auth_guest_token(int(uid), password)
   else: self.auth_token_inspect(access_token)
   self.MajorLogin()
   self.GetLoginData()
   return self._build_api_response(self.TAO_PACKET_XT())
  except Exception as e: pass
 
 def _build_api_response(self, authpacket):
  if not self._data.login_token: return "account not found"
  data = gringay.tokendecode(self._data.login_token)
  if self._data.guild_id:
   guild = {}
   guild["id"] = self._data.guild_id
   guild["secret_code"] = self._data.guild_code
  else: guild = False

  saddress = {}
  saddress["chatip"] = self._data.chat_ip
  saddress["chatport"] = self._data.chat_port
  saddress["onlineip"] = self._data.online_ip
  saddress["onlineport"] = self._data.online_port  
  response = {}
  response["CreateTime"] = gringay.format_timestamp(self._data.create_time)
  response["ExpiryTime"] = gringay.format_timestamp(self._data.expiry_time)
  response["UserAuthPacket"] = list(authpacket)
  response["UserAuthToken"] = self._data.login_token
  response["UserNickName"] = data.get("nickname")
  response["UserAccountUID"] = data.get("account_id")
  response["LockRegion"] = data.get("lock_region")
  response["ClientVersion"] = data.get("client_version")
  response["IsEmulator"] = data.get("is_emulator")
  response["GuildData"] = guild
  response["BaseUrl"] = self._data.base_url or ""
  response["key"] = list(self._data.key)
  response["iv"] = list(self._data.iv)
  response["logindata"] = self.logindata
  response["GameServerAddress"] = saddress
  return response

class FreeFireAPI: 
 def __init__(self):
  self.client = APIClient()
 def get(self, target: str, is_emulator: bool = False):
  return self.client.auth(target, is_emulator)