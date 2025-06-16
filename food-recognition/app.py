import os
import threading
import argparse
import getpass
from openai import OpenAI
from flask_cors import CORS
from pyngrok import ngrok, conf
from backend.routes import set_routes
from backend.constants import UPLOAD_FOLDER, CSV_FOLDER, DETECTION_FOLDER, SEGMENTATION_FOLDER, METADATA_FOLDER
from backend.models import db, User
from werkzeug.security import generate_password_hash, check_password_hash
from backend.models import AnalysisHistory
from flask import Flask, render_template, request, redirect, url_for, flash, session
from backend.routes import build_prompt
from openai import OpenAI
from backend.utils import *



client = OpenAI(
    api_key="sk-58530a01a7a94d66a92c010a8a86f0a9",
    base_url="https://api.deepseek.com"
)
def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['SECRET_KEY'] = 'sk-58530a01a7a94d66a92c010a8a86f0a9'  # 换成你自己的
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    db.init_app(app)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['CSV_FOLDER'] = CSV_FOLDER
    app.config['DETECTION_FOLDER'] = DETECTION_FOLDER
    app.config['SEGMENTATION_FOLDER'] = SEGMENTATION_FOLDER

    set_routes(app)

    # -------- 用户登录 --------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['username'] = user.username
                flash('Login successful!')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password')
                return redirect(url_for('login'))
        # GET 请求时什么都不 flash！
        return render_template('login.html', show_register=False)


    # -------- 用户主页 dashboard --------
    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))
        return render_template('dashboard.html', username=session.get('username'))

    # -------- 用户注册 --------
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            if User.query.filter_by(username=username).first():
                flash('Username already exists')
                return redirect(url_for('register'))
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            # 注册成功，自动登录
            session['user_id'] = new_user.id
            session['username'] = new_user.username
            flash('Registration successful! You are now logged in.')
            return redirect(url_for('dashboard'))
        return render_template('login.html', show_register=True)

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out.')
        return redirect(url_for('login'))

    @app.route('/upload', methods=['GET', 'POST'])
    def upload_food():
        if request.method == 'POST':
            file = request.files.get('file')
            if not file:
                flash('No file uploaded')
                return redirect(url_for('upload_food'))

            # 1. 保存上传
            filename, filepath, filetype = process_upload_file(request)

            # 2. 检测（多返回 result_dict）
            out_name, output_path, output_type, result_dict = process_image_file(
                filename,
                filepath,
                "yolov5s",  # 小写且 weight_urls 里有的名字
                False,  # tta
                False,  # ensemble
                0.15,  # min_conf
                0.5,  # min_iou
                False,  # enhanced
                False  # segmentation
            )

            # 3. 读取csv结果（你如果后面不再需要csv，可以直接用 result_dict 解析食物和营养成分）
            _, csv_name1, csv_name2 = process_output_file(output_path)

            # -------- 推荐直接从 result_dict 提取（最高置信度的食物和营养），这样不依赖 csv ----------
            # 假如 result_dict 结构是 {'names': [...], 'scores': [...], ...}
            # 选置信度最高的
            if result_dict and 'names' in result_dict and 'scores' in result_dict:
                idx = int(np.argmax(result_dict['scores']))
                food_name = result_dict['names'][idx]
                # nutrients 部分如果 result_dict 里有，也直接提取。否则继续用 extract_food_and_nutrients(csv_name1)
                nutrients = {}
                # 例如 result_dict 可能有 'calories', 'protein', ...都可提取
                for k in ['calories', 'protein', 'fat', 'carbs', 'fiber']:
                    if k in result_dict:
                        try:
                            nutrients[k] = result_dict[k][idx]
                        except Exception:
                            pass
            else:
                # 保底还是按 csv 方式
                food_name, nutrients = extract_food_and_nutrients(csv_name1)

            # 4. 调用 LLM
            data = {"food": food_name, "nutrients": nutrients, "user_info": session.get('username', '')}
            prompt = build_prompt(data)
            ai_advice = ""
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "You are a professional nutritionist."},
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                ai_advice = response.choices[0].message.content
            except Exception as e:
                ai_advice = f"AI analysis failed: {e}"

            # 5. 保存历史，渲染
            # ...略...

            return render_template(
                'analyze_result.html',
                food_name=food_name,
                nutrients=nutrients,
                ai_advice=ai_advice
            )
        return render_template('upload_file.html')

    return app






parser = argparse.ArgumentParser('Online Food Recognition')
parser.add_argument('--ngrok', action='store_true', default=False, help="Run on local or ngrok")
parser.add_argument('--host', type=str, default='localhost', help="Local IP")
parser.add_argument('--port', type=int, default=5000, help="Local port")
parser.add_argument('--debug', action='store_true', default=False, help="Run app in debug mode")
args = parser.parse_args()

if __name__ == '__main__':
    app = create_app()

    for folder in [UPLOAD_FOLDER, DETECTION_FOLDER, SEGMENTATION_FOLDER, CSV_FOLDER, METADATA_FOLDER]:
        os.makedirs(folder, exist_ok=True)

    if args.ngrok:
        print("Enter your authtoken, which can be copied from https://dashboard.ngrok.com/get-started/your-authtoken")
        conf.get_default().auth_token = getpass.getpass()
        public_url = ngrok.connect(args.port).public_url
        print(f" * ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:{args.port}/\"")
        app.config['BASE_URL'] = public_url
    else:
        app.config['BASE_URL'] = f"http://{args.host}:{args.port}"

    app.run(host=args.host, port=args.port, debug=True)
