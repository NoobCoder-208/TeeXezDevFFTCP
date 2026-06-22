import json, socket, threading, time, logging, sys, requests
from teexez.ReQAPI import FreeFireAPI, protobuf_dec
from teexez.GPackGEN import GPackGEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger("TxTCP")

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
                sock.settimeout(30)
                sock.connect((self.online_ip, int(self.online_port)))
                sock.sendall(self.packet_auth)
                self.sock_online = sock
                log.info("Online connected")
                while self.running.is_set():
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break
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
                    "[FFFFFF][00FFFF]/6 [FFA500]<uid>[FFFFFF] \u279c M\u1edf team 6 ng\u01b0\u1eddi\n\n"
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
