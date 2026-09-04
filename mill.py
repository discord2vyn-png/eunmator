import os
import sqlite3
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

banned_ips = set()
chat_history = []

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>은마터 & 승마터</title>
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; background-color: #1a1a2e; color: #fff; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; position: relative; }
        
        /* 왼쪽 고정 설명 탭 */
        .left-sidebar { position: absolute; left: 20px; top: 20px; width: 280px; display: flex; flex-direction: column; gap: 10px; }
        .tab-btn { background: #0f3460; color: #a0a0a0; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight: bold; text-align: left; box-shadow: 0 4px 10px rgba(0,0,0,0.3); transition: 0.2s; }
        .tab-btn:hover { background: #1b4975; color: white; }
        .tab-btn.active { background: #e94560; color: white; }

        .intro-container { display: flex; flex-direction: column; gap: 10px; }
        .world-box { background: #16213e; padding: 12px; border-radius: 8px; border: 2px solid #0f3460; font-size: 13px; line-height: 1.4; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .world-box h4 { margin: 0 0 5px 0; color: #e94560; font-size: 14px; }
        
        /* 중앙 메인 컨테이너 */
        .container { width: 100%; max-width: 550px; background: #16213e; padding: 20px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); margin-top: 0; }
        h1 { color: #e94560; text-align: center; margin-top: 0; }
        
        .section { display: flex; flex-direction: column; gap: 15px; margin-top: 20px; }
        .hidden { display: none !important; }
        
        .input-group { display: flex; flex-direction: column; gap: 5px; }
        .input-group label { font-size: 14px; color: #a0a0a0; }
        
        .password-wrapper { display: flex; position: relative; }
        .password-wrapper input { flex: 1; padding: 12px; border: 1px solid #0f3460; background: #1a1a2e; color: white; border-radius: 5px; font-size: 16px; padding-right: 45px; }
        .toggle-pw { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; color: #a0a0a0; cursor: pointer; font-size: 14px; padding: 5px; }
        
        .input-group input:not(.password-wrapper input) { padding: 12px; border: 1px solid #0f3460; background: #1a1a2e; color: white; border-radius: 5px; font-size: 16px; }

        .btn-row { display: flex; gap: 10px; }
        button { flex: 1; padding: 12px; background: #e94560; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 16px; }
        button:hover { background: #cc334d; }
        button.secondary { background: #0f3460; }
        button.secondary:hover { background: #1b4975; }
        
        .room-selector { display: flex; gap: 10px; margin-bottom: 10px; }
        .room-tab { flex: 1; padding: 10px; background: #0f3460; border: none; color: #a0a0a0; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .room-tab.active-room { background: #e94560; color: white; }

        #chat-box { height: 300px; border: 1px solid #0f3460; border-radius: 5px; overflow-y: scroll; padding: 10px; margin-bottom: 10px; background: #1a1a2e; }
        .message { margin-bottom: 8px; font-size: 15px; }
        .message span.name { color: #e94560; font-weight: bold; }
        
        .input-area { display: flex; gap: 10px; }
        .input-area input { flex: 1; padding: 10px; border: 1px solid #0f3460; background: #1a1a2e; color: white; border-radius: 5px; }
        
        .admin-panel { background: #2c1a1d; border: 1px solid #e94560; padding: 10px; border-radius: 5px; margin-bottom: 10px; display: flex; gap: 10px; align-items: center; }
        .admin-panel input { padding: 6px; background: #1a1a2e; border: 1px solid #e94560; color: white; border-radius: 3px; }
        .admin-panel button { padding: 6px 12px; font-size: 13px; }
        
        .voice-panel { background: #122338; border: 1px solid #3498db; padding: 10px; border-radius: 5px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
    </style>
</head>
<body>
    <!-- 왼쪽 고정 사이드바 (설명 탭 및 은마/승마 네모 박스 설명) -->
    <div class="left-sidebar" id="left-sidebar">
        <button id="nav-desc-btn" class="tab-btn" onclick="toggleDescTab()">📖 세계관 설명 탭</button>
        <div class="intro-container hidden" id="intro-box">
            <!-- 은마 설명 네모 박스 -->
            <div class="world-box">
                <h4>은마터 세계관</h4>
                은마는 <strong>은빛마법사</strong>를 뜻합니다. 은빛마법사가 세상을 배신하자 사람들은 저주를 걸어 그를 터트려버렸고, 이 비극적인 사건을 <strong>'은마터'</strong>라 부르게 되었습니다.
            </div>
            <!-- 승마 설명 네모 박스 -->
            <div class="world-box">
                <h4>승마터 세계관</h4>
                승마는 <strong>승리의 악마</strong>를 뜻합니다. 승리를 너무 좋아하는 악마라 승리만을 추구하다 신들에게 터트려져 세상에 사라졌고, 이 비극적인 사건을 <strong>'승마터'</strong>라고 합니다.
            </div>
        </div>
    </div>

    <div class="container">
        <h1>은마 & 승마 사이트</h1>

        <!-- 로그인 전 룸 선택 (은마방 / 승마방) -->
        <div id="room-select-section" class="room-selector">
            <button class="room-tab active-room" id="btn-room-enma" onclick="selectRoom('은마방')">은마방</button>
            <button class="room-tab" id="btn-room-seungma" onclick="selectRoom('승마방')">승마방</button>
        </div>

        <!-- 로그인 탭 -->
        <div id="login-section" class="section">
            <h3 style="margin: 0; color: #e94560; text-align: center;" id="login-title">은마방 로그인</h3>
            <div class="input-group">
                <label>아이디</label>
                <input type="text" id="login-username" placeholder="아이디 입력">
            </div>
            <div class="input-group">
                <label>비밀번호</label>
                <div class="password-wrapper">
                    <input type="password" id="login-password" placeholder="비밀번호 입력">
                    <button type="button" class="toggle-pw" onclick="togglePassword('login-password', this)">👁️</button>
                </div>
            </div>
            <div class="btn-row">
                <button onclick="login()">로그인</button>
                <button class="secondary" onclick="switchTab('register')">회원가입으로 가기</button>
            </div>
        </div>

        <!-- 회원가입 탭 -->
        <div id="register-section" class="section hidden">
            <h3 style="margin: 0; color: #e94560; text-align: center;">회원가입</h3>
            <div class="input-group">
                <label>사용할 아이디</label>
                <input type="text" id="reg-username" placeholder="아이디 입력">
            </div>
            <div class="input-group">
                <label>사용할 비밀번호</label>
                <div class="password-wrapper">
                    <input type="password" id="reg-password" placeholder="비밀번호 입력">
                    <button type="button" class="toggle-pw" onclick="togglePassword('reg-password', this)">👁️</button>
                </div>
            </div>
            <div class="btn-row">
                <button onclick="register()">가입하기</button>
                <button class="secondary" onclick="switchTab('login')">로그인으로 가기</button>
            </div>
        </div>

        <!-- 채팅 및 음성 소통 화면 -->
        <div id="chat-section" class="section hidden">
            <h3 id="current-room-title" style="margin: 0; text-align: center; color: #e94560;">채팅방</h3>
            
            <div id="admin-controls" class="admin-panel hidden">
                <span style="color: #e94560; font-weight: bold; font-size: 13px;">[관리자]</span>
                <input type="text" id="ban-ip-input" placeholder="차단할 IP 입력">
                <button onclick="kickUser()">IP 밴</button>
                <button class="secondary" onclick="clearChat()">채팅 초기화</button>
            </div>

            <div class="voice-panel">
                <span>🎤 실시간 음성 소통</span>
                <div>
                    <button id="voice-btn" onclick="toggleVoice()" style="padding: 6px 12px; font-size: 13px; background: #27ae60;">음성 연결</button>
                </div>
            </div>
            <audio id="remote-audio" autoplay></audio>

            <div id="chat-box"></div>
            
            <div class="input-area">
                <input type="text" id="message-input" placeholder="메시지를 입력하세요..." onkeypress="checkEnter(event)">
                <button onclick="sendMessage()">보내기</button>
            </div>
        </div>
    </div>

    <!-- Socket.IO 라이브러리 -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <script>
        const socket = io();
        let myName = "";
        let currentRoom = "은마방";
        let localStream = null;
        let peerConnection = null;

        const servers = {
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        };

        function selectRoom(roomName) {
            currentRoom = roomName;
            document.getElementById('btn-room-enma').classList.remove('active-room');
            document.getElementById('btn-room-seungma').classList.remove('active-room');
            
            if (roomName === '은마방') {
                document.getElementById('btn-room-enma').classList.add('active-room');
                document.getElementById('login-title').innerText = '은마방 로그인';
            } else {
                document.getElementById('btn-room-seungma').classList.add('active-room');
                document.getElementById('login-title').innerText = '승마방 로그인';
            }
        }

        function toggleDescTab() {
            const introBox = document.getElementById('intro-box');
            const descBtn = document.getElementById('nav-desc-btn');
            if (introBox.classList.contains('hidden')) {
                introBox.classList.remove('hidden');
                descBtn.classList.add('active');
            } else {
                introBox.classList.add('hidden');
                descBtn.classList.remove('active');
            }
        }

        function switchTab(tabName) {
            if (tabName === 'login') {
                document.getElementById('register-section').classList.add('hidden');
                document.getElementById('login-section').classList.remove('hidden');
                document.getElementById('room-select-section').classList.remove('hidden');
            } else {
                document.getElementById('login-section').classList.add('hidden');
                document.getElementById('room-select-section').classList.add('hidden');
                document.getElementById('register-section').classList.remove('hidden');
            }
        }

        function togglePassword(fieldId, btn) {
            const inputField = document.getElementById(fieldId);
            if (inputField.type === "password") {
                inputField.type = "text";
                btn.style.color = "#e94560";
            } else {
                inputField.type = "password";
                btn.style.color = "#a0a0a0";
            }
        }

        function register() {
            const username = document.getElementById('reg-username').value.trim();
            const password = document.getElementById('reg-password').value.trim();
            if (!username || !password) { alert('아이디와 비밀번호를 입력하세요.'); return; }
            socket.emit('register_request', { username, password });
        }

        function login() {
            const username = document.getElementById('login-username').value.trim();
            const password = document.getElementById('login-password').value.trim();
            if (!username || !password) { alert('아이디와 비밀번호를 입력하세요.'); return; }
            socket.emit('login_request', { username, password, room: currentRoom });
        }

        socket.on('auth_response', function(data) {
            if (data.status === 'success') {
                if (data.action === 'register') {
                    alert('회원가입이 완료되었습니다! 로그인해 주세요.');
                    switchTab('login');
                    return;
                }

                myName = data.username;
                document.getElementById('login-section').classList.add('hidden');
                document.getElementById('register-section').classList.add('hidden');
                document.getElementById('room-select-section').classList.add('hidden');
                document.getElementById('left-sidebar').classList.add('hidden'); // 로그인 후 왼쪽 설명탭 숨김
                document.getElementById('chat-section').classList.remove('hidden');
                document.getElementById('current-room-title').innerText = `[${data.room}] 채팅방`;

                if (myName === 'admin') {
                    document.getElementById('admin-controls').classList.remove('hidden');
                }

                const chatBox = document.getElementById('chat-box');
                chatBox.innerHTML = "";
                data.history.forEach(msg => appendMessage(msg));
            } else {
                alert(data.message);
            }
        });

        socket.on('banned', function() {
            alert('관리자에 의해 차단(IP 밴)되었습니다.');
            window.location.reload();
        });

        socket.on('chat_cleared', function() {
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML = "";
            const div = document.createElement('div');
            div.className = 'message';
            div.innerHTML = `<span style="color: #f39c12; font-style: italic;">[시스템] 관리자에 의해 채팅이 초기화되었습니다.</span>`;
            chatBox.appendChild(div);
        });

        socket.on('broadcast_message', function(data) {
            appendMessage(data);
        });

        function appendMessage(data) {
            const chatBox = document.getElementById('chat-box');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message';
            
            if (data.name === "시스템") {
                messageDiv.innerHTML = `<span style="color: #f39c12; font-style: italic;">${data.text}</span>`;
            } else {
                messageDiv.innerHTML = `<span class="name">[${data.name}]</span>: ${data.text}`;
            }
            
            chatBox.appendChild(messageDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('message-input');
            const text = input.value.trim();
            if (text !== "") {
                socket.emit('message_from_user', { name: myName, text: text, room: currentRoom });
                input.value = "";
            }
        }

        function checkEnter(event) {
            if (event.key === 'Enter') { sendMessage(); }
        }

        function kickUser() {
            const ip = document.getElementById('ban-ip-input').value.trim();
            if (!ip) { alert('차단할 IP를 입력하세요.'); return; }
            socket.emit('admin_ban_ip', { ip: ip });
            alert(`${ip} 주소를 차단했습니다.`);
            document.getElementById('ban-ip-input').value = "";
        }

        function clearChat() {
            if (confirm('채팅 기록을 전부 초기화하시겠습니까?')) {
                socket.emit('admin_clear_chat', { room: currentRoom });
            }
        }

        async function toggleVoice() {
            const btn = document.getElementById('voice-btn');
            if (!localStream) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
                    btn.textContent = "음성 해제";
                    btn.style.background = "#c0392b";
                    
                    socket.emit('join_voice', { room: currentRoom });
                    setupPeerConnection();
                } catch (err) {
                    alert('마이크 권한을 허용해야 음성 통화가 가능합니다.');
                }
            } else {
                localStream.getTracks().forEach(track => track.stop());
                localStream = null;
                if (peerConnection) { peerConnection.close(); peerConnection = null; }
                btn.textContent = "음성 연결";
                btn.style.background = "#27ae60";
                socket.emit('leave_voice', { room: currentRoom });
            }
        }

        function setupPeerConnection() {
            peerConnection = new RTCPeerConnection(servers);
            localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

            peerConnection.ontrack = event => {
                document.getElementById('remote-audio').srcObject = event.streams[0];
            };

            peerConnection.onicecandidate = event => {
                if (event.candidate) {
                    socket.emit('voice_candidate', { candidate: event.candidate, room: currentRoom });
                }
            };

            socket.on('voice_offer', async offer => {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(offer));
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                socket.emit('voice_answer', { answer: answer, room: currentRoom });
            });

            socket.on('voice_answer', async answer => {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
            });

            socket.on('voice_candidate', async candidate => {
                if (peerConnection) {
                    await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
                }
            });

            socket.on('peer_joined', async () => {
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                socket.emit('voice_offer', { offer: offer, room: currentRoom });
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@socketio.on('register_request')
def handle_register(data):
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        socketio.emit('auth_response', {'status': 'success', 'action': 'register'}, room=request.sid)
    except sqlite3.IntegrityError:
        socketio.emit('auth_response', {'status': 'fail', 'message': '이미 존재하는 아이디입니다.'}, room=request.sid)
    finally:
        conn.close()

@socketio.on('login_request')
def handle_login(data):
    client_ip = request.remote_addr
    if client_ip in banned_ips:
        socketio.emit('banned', room=request.sid)
        return

    username = data.get('username')
    password = data.get('password')
    room = data.get('room', '은마방')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0] == password:
        room_history = [m for m in chat_history if m.get('room') == room]
        socketio.emit('auth_response', {'status': 'success', 'action': 'login', 'username': username, 'room': room, 'history': room_history}, room=request.sid)
    else:
        socketio.emit('auth_response', {'status': 'fail', 'message': '아이디 또는 비밀번호가 틀렸습니다.'}, room=request.sid)

@socketio.on('message_from_user')
def handle_message(data):
    global chat_history
    chat_history.append(data)
    if len(chat_history) > 200:
        chat_history.pop(0)
    room = data.get('room', '은마방')
    socketio.emit('broadcast_message', data, room=room)

@socketio.on('admin_ban_ip')
def handle_ban(data):
    target_ip = data.get('ip')
    banned_ips.add(target_ip)
    socketio.emit('banned')

@socketio.on('admin_clear_chat')
def handle_clear_chat(data):
    global chat_history
    room = data.get('room', '은마방')
    chat_history = [m for m in chat_history if m.get('room') != room]
    socketio.emit('chat_cleared', room=room)

@socketio.on('join_voice')
def handle_join_voice(data):
    room = data.get('room', '은마방') + '_voice'
    join_room(room)
    socketio.emit('peer_joined', room=room, skip_sid=request.sid)

@socketio.on('leave_voice')
def handle_leave_voice(data):
    pass

@socketio.on('voice_offer')
def handle_voice_offer(data):
    room = data.get('room', '은마방') + '_voice'
    socketio.emit('voice_offer', data['offer'], room=room, skip_sid=request.sid)

@socketio.on('voice_answer')
def handle_voice_answer(data):
    room = data.get('room', '은마방') + '_voice'
    socketio.emit('voice_answer', data['answer'], room=room, skip_sid=request.sid)

@socketio.on('voice_candidate')
def handle_voice_candidate(data):
    room = data.get('room', '은마방') + '_voice'
    socketio.emit('voice_candidate', data['candidate'], room=room, skip_sid=request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)