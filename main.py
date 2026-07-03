import json, socket, threading, time, logging, sys, requests, random
from teexez.ReQAPI import FreeFireAPI, protobuf_dec, ProtoBuf
from teexez.GPackGEN import GPackGEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger("TeeXezDevTCP")

def read_config():
    with open("bot.txt") as f:
        data = json.load(f)
    for uid, token in data.items():
        return uid, token
    return None, None

LIKE_API = "https://teexezlike-ob5l.onrender.com/likes?uid=%s"

def send_likes(uid):
    try:
        resp = requests.get(LIKE_API % uid, timeout=30)
        data = resp.json()
    except requests.Timeout:
        return "[B][c][FF0000]API timeout"
    except Exception as e:
        return "[B][c][FF0000]L%E1%BB%97i: %s" % str(e)[:60]

    if "result" not in data:
        err = data.get("False") or data.get("Failed") or data.get("error") or data.get("message") or str(data)
        return "[B][c][FF0000]%s" % str(err)[:80]

    r = data["result"]
    nick = r["User Info"]["Account Name"]
    level = r["User Info"]["Account Level"]
    region = r["User Info"]["Account Region"]
    added = r["Likes Info"]["Likes Added"]
    before = r["Likes Info"]["Likes Before"]
    after = r["Likes Info"]["Likes After"]
    speed = r["API"]["speeds"]

    return (
        "[B][C][00FF00]T\u0103ng like th\u00e0nh c\u00f4ng!\n\n"
        "[FFFFFF]Nickname: [00FFFF]{}\n"
        "[FFFFFF]Level: [FFFF00]{}\n"
        "[FFFFFF]Khu v\u1ef1c: [FFA500]{}\n\n"
        "[FFFFFF]Likes th\u00eam: [00FF00]+{}\n"
        "[FFFFFF]Likes ban \u0111\u1ea7u: [FFA500]{}\n"
        "[FFFFFF]T\u1ed5ng s\u1ed1 like: [00FF00]{}\n\n"
        "[AAAAAA]T\u1ed1c \u0111\u1ed9: {}"
    ).format(nick, level, region, added, before, after, speed)

def extract_uid_fields(parsed):
    uids, seen = [], set()
    def add(v):
        if isinstance(v, str) and v.isdigit(): v = int(v)
        if isinstance(v, int) and v not in seen:
            seen.add(v); uids.append(v)
    if "1" in parsed: add(parsed["1"])
    f5 = parsed.get("5")
    if isinstance(f5, dict):
        if "1" in f5: add(f5["1"])
        members = f5.get("6")
        if isinstance(members, list):
            for item in members:
                if isinstance(item, dict) and "1" in item:
                    add(item["1"])
    return uids

def ChooseEmote(token, url):
    url = "{}/ChooseEmote".format(url.rstrip("/"))
    headers = {
        "ReleaseVersion": "OB53", "X-GA": "v1 1",
        "Authorization": "Bearer {}".format(token)}
    data = "5D 16 45 26 18 C5 DE 3E E8 F4 C5 36 03 7F 84 B7"
    try:
        requests.post(url, data=bytes.fromhex(data), headers=headers, timeout=10)
    except:
        pass

class datamsg:
    def __init__(self, data):
        self.valid = False
        try:
            info = json.loads(protobuf_dec(data.hex()[10:])).get("5", {})
            if not isinstance(info, dict):
                return
            self.tp = info.get("3")
            if self.tp == 1:
                self.uid, self.cid = str(info["1"]), str(info["2"])
            elif self.tp == 2:
                self.uid = self.cid = str(info["1"])
            else:
                self.uid = self.cid = str(info.get("1", ""))
            self.name = info.get("9", {}).get("1", "")
            self.message = ("/bot" if "8" in info else info.get("4", "")).lower()
            self.valid = True
        except:
            self.uid = self.cid = self.name = self.message = self.tp = None

class Bot:
    def __init__(self, uid, token):
        self.uid = uid
        self.token = token
        self.chat_ip = self.chat_port = self.online_ip = self.online_port = ""
        self.packet_auth = None
        self.botid = self.nickname = None
        self.guild_id = self.guild_code = None
        self.sock_chat = self.sock_online = None
        self.running = threading.Event()
        self._gen = None
        self.insquad = None
        self.joining_team = False
        self.ids = []
        self._stop_all = False
        self.Emotes = {
            'E1': 909050020, 'E2': 909050009, 'G18': 909038012, 'CGK': 909042008,
            'AK47': 909000063, 'MP40': 909000075, 'MP40V2': 909040010,
            'FAMAS': 909000090, 'PRF': 909045001, 'M1014V2': 909039011,
            'P90': 909049010, 'UMP': 909000098, 'GROZA': 909041005, "E3": 909051002,
            'MP5': 909033002, 'XM8': 909000085, 'M4A1': 909033001, "M60": 909051003,
            'M1887': 909035007, 'LEVEL100': 909042007, 'M1014': 909000081
        }

    def cleanup(self):
        self.running.clear()
        for s in [self.sock_chat, self.sock_online]:
            try: s.close()
            except: pass
        self.sock_chat = self.sock_online = None

    def run(self):
        self.running.set()
        while self.running.is_set():
            try:
                cred = "%s:%s" % (self.uid, self.token)
                data = FreeFireAPI().get(cred, is_emulator=False)
                if not data or "account not found" in data:
                    log.error("Account not found")
                    break

                self.packet_auth = bytes(data["UserAuthPacket"])
                self.botid = int(data["UserAccountUID"])
                ld4 = data["logindata"].get("4")
                self.nickname = str(ld4) if ld4 else str(data["UserNickName"])
                self.chat_ip = data["GameServerAddress"]["chatip"]
                self.chat_port = data["GameServerAddress"]["chatport"]
                self.online_ip = data["GameServerAddress"]["onlineip"]
                self.online_port = data["GameServerAddress"]["onlineport"]
                self._gen = GPackGEN(data["logindata"], data)
                gd = data.get("GuildData")
                self.guild_id = gd.get("id") if gd else None
                self.guild_code = gd.get("secret_code") if gd else None
                log.info("Authenticated: %s | %s", self.botid, self.nickname)
                if data.get("UserAuthToken") and data.get("BaseUrl"):
                    threading.Thread(target=ChooseEmote, args=(data["UserAuthToken"], data["BaseUrl"]), daemon=True).start()

                t1 = threading.Thread(target=self._conn_chat, daemon=True)
                t2 = threading.Thread(target=self._conn_online, daemon=True)
                t1.start()
                t2.start()
                t1.join()
                t2.join()

                if not self.running.is_set():
                    break
                log.info("Reconnecting auth in 30s...")
                time.sleep(30)
            except Exception as e:
                log.error("run(): %s", e)
                if self.running.is_set():
                    time.sleep(10)

    def _conn_chat(self):
        while self.running.is_set():
            try:
                sock = socket.create_connection((self.chat_ip, int(self.chat_port)), timeout=15)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.sendall(self.packet_auth)
                if self.guild_id and self.guild_code:
                    sock.sendall(self._gen.join_channel(self.guild_id, self.guild_code, 1))
                sock.sendall(self._gen.join_channel(None, None, 5))
                self.sock_chat = sock
                log.info("Chat connected")
                sock.settimeout(120)
                while self.running.is_set():
                    try:
                        data = sock.recv(3300)
                        if not data:
                            break
                        if data.hex()[:4] == "1200" and len(data) > 50:
                            self._handle_chat(data)
                    except socket.timeout:
                        continue
            except Exception as e:
                log.warning("Chat error: %s", e)
            finally:
                try: sock.close()
                except: pass
                self.sock_chat = None
                if self.running.is_set():
                    time.sleep(5)

    def _conn_online(self):
        while self.running.is_set():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.settimeout(30)
                sock.connect((self.online_ip, int(self.online_port)))
                sock.sendall(self.packet_auth)
                self.sock_online = sock
                log.info("Online connected")
                last_reset = time.time()
                while self.running.is_set():
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break
                        if data.hex()[:4] == "0500":
                            self._process_0500_packet(data)
                        now = time.time()
                        if now - last_reset > 5:
                            if self.insquad is not None:
                                self.insquad = None
                                self.joining_team = False
                            last_reset = now
                    except socket.timeout:
                        continue
            except Exception as e:
                log.warning("Online error: %s", e)
            finally:
                try: sock.close()
                except: pass
                self.sock_online = None
                if self.running.is_set():
                    time.sleep(3)

    def _handle_chat(self, data):
        msg = datamsg(data)
        if not msg.valid:
            return
        if not msg.message:
            return
        if str(self.botid) in (msg.cid, msg.uid):
            return
        try:
            text = msg.message
            if text in ("help", "/help"):
                self._reply(msg.cid, msg.tp,
                    "[B][C][00FF00]Danh s\xe1\xbb\x93ch l\u1ec7nh\n\n"
                    "[FFFFFF][00FFFF]/help [FFFFFF]\u279c Xem danh s\xe1\xbb\x93ch l\u1ec7nh\n"
                    "[FFFFFF][00FFFF]/like [FFA500]<uid>[FFFFFF] \u279c T\u0103ng likes cho ng\u01b0\u1eddi ch\u01a1i\n"
                    "[FFFFFF][00FFFF]/5 [FFA500]<uid>[FFFFFF] \u279c M\u1edf team 5 ng\u01b0\u1eddi\n"
                    "[FFFFFF][00FFFF]/6 [FFA500]<uid>[FFFFFF] \u279c M\u1edf team 6 ng\u01b0\u1eddi\n"
                    "[FFFFFF][00FFFF]/js [FFA500]<teamcode>[FFFFFF] \u279c V\xe0o team b\u1eb1ng code\n"
                    "[FFFFFF][00FFFF]/cut [FFFFFF]\u279c Tho\xe1t team\n"
                    "[FFFFFF][00FFFF]/all s7 [FFFFFF]\u279c B\u1eadt h\xe0nh \u0111\u1ed9ng all\n"
                    "[FFFFFF][00FFFF]/all rd s7 [FFFFFF]\u279c Random h\xe0nh \u0111\u1ed9ng all\n"
                    "[FFFFFF][00FFFF]/share [FFA500]<uid>[FFFFFF] \u279c Y\xeau c\u1ea7u share \u0111\u1ed3\n"
                    "[FFFFFF][00FFFF]/dung [FFFFFF]\u279c D\u1eebng m\xfaa /all\n\n"
                    "[AAAAAA]--- TeeXez ---"
                )
                return
            if text.startswith(("/like", "/likes")):
                parts = text.split()
                if len(parts) < 2 or not parts[1].isdigit():
                    self._reply(msg.cid, msg.tp, "[B][c][FF0000]/like <uid>")
                    return
                self._reply(msg.cid, msg.tp, "[B][c][FFFF00]\u0110ang t\u0103ng likes...")
                result = send_likes(parts[1])
                self._reply(msg.cid, msg.tp, result)
                log.info("/like -> %s", parts[1])
                return
            if text in ("/5", "/6"):
                threading.Thread(target=self._gen_squads, args=(int(text[1]), msg.cid, msg.uid, msg.tp), daemon=True).start()
                return
            if text.startswith(("/5 ", "/6 ")):
                parts = text.split()
                if len(parts) < 2 or not parts[1].isdigit():
                    self._reply(msg.cid, msg.tp, "[B][c][FF0000]/%s <uid>" % text[1])
                    return
                threading.Thread(target=self._gen_squads, args=(int(text[1]), msg.cid, parts[1], msg.tp), daemon=True).start()
                return
            if text.startswith("/js"):
                parts = text.split()
                if len(parts) < 2 or not parts[1].isdigit():
                    self._reply(msg.cid, msg.tp, "[B][c][FF0000]/js <teamcode>")
                    return
                self._reply(msg.cid, msg.tp, "[B][c][FFFF00]\u0110ang v\xe0o team %s..." % parts[1])
                try:
                    if self.sock_chat and self._gen:
                        self.sock_chat.sendall(self._gen.leave_channel(msg.cid))
                        time.sleep(0.3)
                    if self.sock_online and self._gen:
                        self.sock_online.sendall(self._gen.join_squad(int(parts[1])))
                    self.insquad = True
                    self._reply(msg.cid, msg.tp, "[B][c][00FF00]\u0110\xe3 v\xe0o team %s!" % parts[1])
                except Exception as e:
                    self._reply(msg.cid, msg.tp, "[B][c][FF0000]L%E1%BB%97i: %s" % str(e)[:50])
                return
            if text.startswith("/all"):
                parts = text.split()
                if len(parts) < 2:
                    self._reply(msg.cid, msg.tp, "[B][c]Dùng: /all s7 hoặc /all rd s7")
                    return
                if not self.ids:
                    self._reply(msg.cid, msg.tp, "[B][c]Vui lòng dùng /js trước")
                    return
                self._stop_all = False
                cc = parts[1].upper()
                if cc == "RD" and len(parts) >= 3 and parts[2].lower() == "s7":
                    threading.Thread(target=self._all_rd_s7, args=(msg.cid, msg.tp), daemon=True).start()
                elif cc == "S7":
                    threading.Thread(target=self._all_s7, args=(msg.cid, msg.tp), daemon=True).start()
                else:
                    self._reply(msg.cid, msg.tp, "[B][c]Dùng: /all s7 hoặc /all rd s7")
                return
            if text in ("/cut", "/leave"):
                try:
                    if self.sock_chat and self._gen:
                        self.sock_chat.sendall(self._gen.leave_channel(msg.cid))
                    if self.sock_online and self._gen:
                        self.sock_online.sendall(self._gen.leave_squad(0))
                    self.insquad = None
                    self.joining_team = False
                    self._reply(msg.cid, msg.tp, "[B][c][00FF00]\u0110\xe3 tho\xe1t team!")
                except Exception as e:
                    self._reply(msg.cid, msg.tp, "[B][c][FF0000]L%E1%BB%97i: %s" % str(e)[:50])
                return
            if text.startswith("/share"):
                parts = text.split()
                target_uid = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else msg.uid
                if not self.sock_online or not self._gen:
                    self._reply(msg.cid, msg.tp, "[B][c][FF0000]L%E1%BB%97i k%E1%BA%BFt n%E1%BB%91i")
                    return
                try:
                    self.sock_online.sendall(self._gen.ask_for_skin(target_uid))
                    self._reply(msg.cid, msg.tp, "[B][c][00FF00]%s" % target_uid)
                except Exception as e:
                    self._reply(msg.cid, msg.tp, "[B][c][FF0000]L%E1%BB%97i: %s" % str(e)[:50])
                return
            if text in ("/dung",):
                self._stop_all = True
                self._reply(msg.cid, msg.tp, "[B][c][FF0000]\u0110\xe3 d\u1eebng h\xe0nh \u0111\u1ed9ng!")
                return
        except Exception as e:
            log.warning("Chat handler: %s | msg: %s", e, msg.message[:50] if msg.message else "")

    def _reply(self, cid, tp, text):
        try:
            if self.sock_chat and self._gen:
                self.sock_chat.sendall(self._gen.send_message(text, tp, cid))
        except Exception as e:
            log.warning("Reply error: %s", e)

    def _gen_squads(self, team, cid, uid, tp):
        try:
            if not self.sock_online or not self._gen:
                self._reply(cid, tp, "[B][c][FF0000]L%E1%BB%97i k%E1%BA%BFt n%E1%BB%91i")
                return
            self._reply(cid, tp, "[B][c][FFFF00]\u0110ang m\u1edf team %d..." % team)
            self.sock_online.sendall(self._gen.open_squad(team))
            time.sleep(0.3)
            self.sock_online.sendall(self._gen.invite_squad(int(uid), 1))
            self.sock_online.sendall(self._gen.invite_squad(int(uid), 2))
            self._reply(cid, tp,
                "[B][c][00FF00]\u0110\xe3 m\u1edf team %d!\n[FFFFFF]UID: %s\n[FFFFFF]H\xe3y ki\u1ec3m tra l\u1eddi m\u1eddi." % (team, uid))
            for _ in range(3):
                if not self.running.is_set():
                    return
                self.sock_online.sendall(self._gen.play_animation(914000002))
                time.sleep(3)
            time.sleep(4)
            self.sock_online.sendall(self._gen.leave_squad(0))
            log.info("Closed squad %d for %s", team, uid)
        except Exception as e:
            log.warning("Squad error: %s", e)

    def _all_s7(self, cid, tp):
        if not self.sock_online or not self._gen or not self.ids:
            self._reply(cid, tp, "[B][c][FF0000]L%E1%BB%97i: ch%01B0a c\xf3 UID ho\u1eb7c m\u1ea5t k\u1ebft n\u1ed1i")
            return
        self._reply(cid, tp, "[B][c][FFFF00]\u0110ang b\u1eadt h\xe0nh \u0111\u1ed9ng all s7...")
        self.sock_online.sendall(self._gen.play_animation(914000002))
        emotes = list(self.Emotes.values())
        for emote in emotes:
            if not self.running.is_set() or self._stop_all: return
            self.sock_online.sendall(self._gen.play_emote(emote, self.ids))
            time.sleep(6.8)
        self._reply(cid, tp, "[B][c][00FF00]Ho\xe0n t\u1ea5t all s7!")
        log.info("/all s7 done")

    def _all_rd_s7(self, cid, tp):
        if not self.sock_online or not self._gen or not self.ids:
            self._reply(cid, tp, "[B][c][FF0000]L%E1%BB%97i: ch%01B0a c\xf3 UID ho\u1eb7c m\u1ea5t k\u1ebft n\u1ed1i")
            return
        self._reply(cid, tp, "[B][c][FFFF00]\u0110ang b\u1eadt random s7...")
        self.sock_online.sendall(self._gen.play_animation(914000002))
        emotes = list(self.Emotes.values())
        random.shuffle(emotes)
        total_ids = len(self.ids)
        idx = 0
        while idx < len(emotes):
            if not self.running.is_set() or self._stop_all: return
            batch = emotes[idx:idx + total_ids]
            for i, uid in enumerate(self.ids):
                if i < len(batch):
                    self.sock_online.sendall(self._gen.play_emote(batch[i], [uid]))
            idx += total_ids
            time.sleep(6.8)
        self._reply(cid, tp, "[B][c][00FF00]Ho\xe0n t\u1ea5t random s7!")
        log.info("/all rd s7 done")

    def _process_0500_packet(self, data):
        try:
            raw = bytes.fromhex(data.hex()[10:])
            parsed = ProtoBuf(raw).protobuf()
        except:
            return

        # Auto-accept invite
        if self.insquad is None and not self.joining_team and self._gen:
            invite = parsed.get("5")
            if isinstance(invite, dict):
                squad_owner = invite.get("1")
                code = invite.get("8")
                if squad_owner and code:
                    try:
                        self.joining_team = True
                        self.sock_online.sendall(self._gen.join_squad_recruit(int(squad_owner), str(code)))
                        time.sleep(1.5)
                        self.insquad = True
                        uid_int = int(squad_owner)
                        if uid_int not in self.ids:
                            self.ids.append(uid_int)
                        if self.sock_chat:
                            self.sock_chat.sendall(self._gen.join_channel(uid_int, str(code), None))
                            time.sleep(0.5)
                            self.sock_chat.sendall(self._gen.send_message("[B][C][00FF00]Chào các em [FFFF00]Anh TeeXez [FFA500]tới chơi", None, uid_int))
                        log.info("Auto-accepted invite from %s | ids: %s", squad_owner, self.ids)
                    except:
                        pass
                    finally:
                        self.joining_team = False

        # Collect UIDs khi đang trong squad
        if self.insquad is not None:
            f4 = parsed.get("4")
            if isinstance(f4, (int, str)):
                log.info("0500 f4=%s ids=%s", f4, self.ids)
                if int(f4) in (3, 6, 8, 44, 56):
                    new = extract_uid_fields(parsed)
                    if new:
                        for uid in new:
                            if uid not in self.ids:
                                self.ids.append(uid)
                        if int(f4) == 6 and self.sock_chat:
                            rc = parsed.get("5", {}).get("17")
                            if rc:
                                for uid in new:
                                    self.sock_chat.sendall(self._gen.join_channel(uid, str(rc), None))
                                    self.sock_chat.sendall(self._gen.send_message("[B][C][00FF00]Chào các em [FFFF00]Anh TeeXez [FFA500]tới chơi", None, uid))
                        log.info("Collected UIDs: %s", new)

def main():
    uid, token = read_config()
    if not uid:
        log.error("No config found in bot.txt")
        return
    log.info("Starting bot: UID=%s", uid)
    while True:
        try:
            bot = Bot(uid, token)
            bot.run()
        except KeyboardInterrupt:
            log.info("Bot stopped by user")
            break
        except Exception as e:
            log.error("Main crash: %s", e)
        log.info("Restarting in 10s...")
        time.sleep(10)

if __name__ == "__main__":
    main()
