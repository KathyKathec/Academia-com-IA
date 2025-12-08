import os
import sys
import cv2
import numpy as np
from datetime import date, datetime
from pathlib import Path
import time

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia.settings')
import django
django.setup()

from gym.models import Cliente, Presenca, ClientePlano

# THRESHOLDS MUITO TOLERANTES
CONFIDENCE_EXCELLENT = 80
CONFIDENCE_GOOD = 100
CONFIDENCE_ACCEPTABLE = 120

COOLDOWN_SEGUNDOS = 5
ultimos_reconhecimentos = {}
ultimo_feedback = {'texto': '', 'cor': (255, 255, 255), 'tempo': 0}

def pode_reconhecer_novamente(client_id):
    agora = time.time()
    if client_id not in ultimos_reconhecimentos:
        return True
    tempo_decorrido = agora - ultimos_reconhecimentos[client_id]
    return tempo_decorrido >= COOLDOWN_SEGUNDOS

def atualizar_cooldown(client_id):
    ultimos_reconhecimentos[client_id] = time.time()

def verificar_acesso_cliente(cliente_id):
    try:
        print(f"[DEBUG] Buscando cliente ID {cliente_id}...")
        cliente = Cliente.objects.get(pk=cliente_id)
        print(f"[DEBUG] Cliente encontrado: {cliente.nome}")
        print(f"[DEBUG] Status ativo: {cliente.status}")
        
        if not cliente.status:
            return False, "Cliente INATIVO", 0
        
        print(f"[DEBUG] Buscando plano ativo...")
        plano_ativo = ClientePlano.objects.filter(cliente=cliente, ativo=True).first()
        
        if not plano_ativo:
            print(f"[DEBUG] Nenhum plano ativo encontrado")
            return False, "SEM PLANO ATIVO", 0
        
        print(f"[DEBUG] Plano ativo encontrado: {plano_ativo.plano.nome}")
        print(f"[DEBUG] Data fim: {plano_ativo.data_fim}")
        
        hoje = date.today()
        print(f"[DEBUG] Data hoje: {hoje}")
        
        if plano_ativo.data_fim < hoje:
            dias_vencido = (hoje - plano_ativo.data_fim).days
            print(f"[DEBUG] Plano vencido ha {dias_vencido} dias")
            return False, f"PLANO VENCIDO ({dias_vencido} dias)", -dias_vencido
        
        dias_restantes = (plano_ativo.data_fim - hoje).days
        print(f"[DEBUG] Dias restantes: {dias_restantes}")
        
        if dias_restantes == 0:
            return True, "VENCE HOJE!", 0
        elif dias_restantes <= 3:
            return True, f"Vence em {dias_restantes} dias", dias_restantes
        else:
            return True, "ACESSO LIBERADO", dias_restantes
            
    except Cliente.DoesNotExist:
        print(f"[DEBUG] Cliente ID {cliente_id} nao existe no banco!")
        return False, "Cliente NAO ENCONTRADO", 0
    except Exception as e:
        print(f"[DEBUG] Erro ao verificar acesso: {e}")
        import traceback
        traceback.print_exc()
        return False, "ERRO AO VERIFICAR", 0

def registrar_presenca(cliente_id):
    try:
        print(f"\n[DEBUG] === INICIANDO REGISTRO DE PRESENCA ===")
        print(f"[DEBUG] Cliente ID: {cliente_id}")
        
        cliente = Cliente.objects.get(pk=cliente_id)
        print(f"[DEBUG] Cliente: {cliente.nome}")
        
        hoje = date.today()
        print(f"[DEBUG] Data: {hoje}")
        
        # Verifica se já existe
        ja_registrado = Presenca.objects.filter(cliente=cliente, data=hoje).exists()
        print(f"[DEBUG] Ja registrado hoje: {ja_registrado}")
        
        if ja_registrado:
            print(f"[INFO] {cliente.nome} ja registrou presenca hoje")
            presenca_existente = Presenca.objects.filter(cliente=cliente, data=hoje).first()
            print(f"[DEBUG] Presenca existente ID: {presenca_existente.id}")
            return True
        
        # Cria presença
        print(f"[DEBUG] Criando nova presenca...")
        presenca = Presenca.objects.create(
            cliente=cliente,
            tipo='facial',
            usuario=None
        )
        
        print(f"[DEBUG] Presenca criada com sucesso!")
        print(f"[DEBUG] Presenca ID: {presenca.id}")
        print(f"[DEBUG] Data: {presenca.data}")
        print(f"[DEBUG] Hora: {presenca.hora_entrada}")
        print(f"[DEBUG] Tipo: {presenca.tipo}")
        
        # Verifica se salvou
        verificacao = Presenca.objects.filter(id=presenca.id).exists()
        print(f"[DEBUG] Verificacao no banco: {verificacao}")
        
        if verificacao:
            print(f"[OK] ✓ Presenca ID {presenca.id} registrada: {cliente.nome}")
            print(f"[DEBUG] === REGISTRO CONCLUIDO COM SUCESSO ===\n")
            return True
        else:
            print(f"[ERRO] Presenca nao foi salva no banco!")
            return False
        
    except Cliente.DoesNotExist:
        print(f"[ERRO] Cliente ID {cliente_id} nao existe!")
        return False
    except Exception as e:
        print(f"[ERRO] Falha ao registrar presenca: {e}")
        import traceback
        traceback.print_exc()
        return False

def pre_processar_face(face_roi):
    """EXATAMENTE IGUAL AO TREINO - SÓ REDIMENSIONA"""
    return cv2.resize(face_roi, (200, 200))

def mostrar_feedback(frame, texto, cor, duracao=3):
    """Mostra feedback na tela por X segundos"""
    global ultimo_feedback
    agora = time.time()
    
    if texto:
        ultimo_feedback = {'texto': texto, 'cor': cor, 'tempo': agora + duracao}
    
    if agora < ultimo_feedback['tempo']:
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 80), (630, 200), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        linhas = ultimo_feedback['texto'].split('\n')
        y = 120
        for linha in linhas:
            cv2.putText(frame, linha, (20, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, ultimo_feedback['cor'], 2)
            y += 35

def reconhecimento_facial():
    trainer_path = Path(__file__).parent / 'trainer.yml'
    
    if not trainer_path.exists():
        print("ERRO: Modelo nao treinado!")
        return
    
    print("\n" + "="*60)
    print("SISTEMA DE RECONHECIMENTO FACIAL")
    print("="*60)
    print(f"[INFO] Thresholds: < {CONFIDENCE_EXCELLENT} (Excelente)")
    print(f"                   < {CONFIDENCE_GOOD} (Bom)")
    print(f"                   < {CONFIDENCE_ACCEPTABLE} (Aceitavel)")
    print(f"[INFO] Cooldown: {COOLDOWN_SEGUNDOS}s")
    print(f"[INFO] Cliente cadastrado: ID 12")
    print("[INFO] Pressione 'Q' para sair")
    print("="*60 + "\n")
    
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_detector = cv2.CascadeClassifier(cascade_path)
    
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(trainer_path))
    
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cam.isOpened():
        print("ERRO: Camera nao acessivel!")
        return
    
    historico_ids = []
    MAX_HISTORICO = 10
    
    reconhecimentos_validos = {}
    FRAMES_MINIMOS = 3
    
    try:
        frame_count = 0
        
        while True:
            ret, frame = cam.read()
            if not ret:
                break
            
            frame_count += 1
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            faces = face_detector.detectMultiScale(
                gray,
                scaleFactor=1.2,
                minNeighbors=5,
                minSize=(100, 100)
            )
            
            if len(faces) == 0:
                reconhecimentos_validos.clear()
                historico_ids.clear()
            
            for (x, y, w, h) in faces:
                face_roi = gray[y:y+h, x:x+w]
                face_processed = pre_processar_face(face_roi)
                
                client_id, confidence = recognizer.predict(face_processed)
                
                print(f"[RAW] ID: {client_id} | Conf: {confidence:.1f}")
                
                if client_id == -1 or confidence > 500:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (128, 128, 128), 1)
                    continue
                
                historico_ids.append(client_id)
                if len(historico_ids) > MAX_HISTORICO:
                    historico_ids.pop(0)
                
                if len(historico_ids) >= 3:
                    from collections import Counter
                    votos = Counter(historico_ids)
                    id_vencedor, num_votos = votos.most_common(1)[0]
                    
                    if num_votos >= len(historico_ids) * 0.5:
                        client_id = id_vencedor
                
                if confidence < CONFIDENCE_EXCELLENT:
                    qualidade = "EXCELENTE"
                    cor = (0, 255, 0)
                    nivel = 3
                elif confidence < CONFIDENCE_GOOD:
                    qualidade = "BOM"
                    cor = (0, 255, 255)
                    nivel = 2
                elif confidence < CONFIDENCE_ACCEPTABLE:
                    qualidade = "ACEITAVEL"
                    cor = (0, 165, 255)
                    nivel = 1
                else:
                    qualidade = "DESCONHECIDO"
                    cor = (0, 0, 255)
                    nivel = 0
                
                try:
                    cliente = Cliente.objects.get(id=client_id)
                    nome = cliente.nome
                except Cliente.DoesNotExist:
                    nome = f"ID {client_id}"
                
                if nivel > 0:
                    if client_id not in reconhecimentos_validos:
                        reconhecimentos_validos[client_id] = 0
                    
                    reconhecimentos_validos[client_id] += 1
                    frames = reconhecimentos_validos[client_id]
                    
                    print(f"[DETECT] ID: {client_id} | Conf: {confidence:.1f} | Frames: {frames}/{FRAMES_MINIMOS}")
                    
                    if frames >= FRAMES_MINIMOS:
                        if pode_reconhecer_novamente(client_id):
                            print(f"\n{'='*60}")
                            print(f"[INFO] PROCESSANDO CLIENTE ID {client_id}")
                            print(f"{'='*60}")
                            
                            # Verifica acesso
                            pode_entrar, mensagem, dias = verificar_acesso_cliente(client_id)
                            
                            print(f"[RESULTADO] Pode entrar: {pode_entrar}")
                            print(f"[RESULTADO] Mensagem: {mensagem}")
                            
                            if pode_entrar:
                                print(f"\n[INFO] Cliente autorizado! Registrando presenca...")
                                
                                # Registra presença
                                sucesso = registrar_presenca(client_id)
                                
                                if sucesso:
                                    cor_final = (0, 255, 0)
                                    feedback_texto = f"ACESSO LIBERADO\n{nome}\n{mensagem}"
                                    
                                    print(f"\n{'*'*60}")
                                    print(f"*** SUCESSO! PRESENCA REGISTRADA! ***")
                                    print(f"*** Cliente: {nome}")
                                    print(f"*** Status: {mensagem}")
                                    print(f"{'*'*60}\n")
                                    
                                    mostrar_feedback(frame, feedback_texto, cor_final, duracao=5)
                                else:
                                    cor_final = (0, 165, 255)
                                    feedback_texto = f"ERRO AO REGISTRAR\n{nome}"
                                    print(f"\n[ERRO] Falha ao registrar presenca!\n")
                                    mostrar_feedback(frame, feedback_texto, cor_final, duracao=3)
                            else:
                                cor_final = (0, 0, 255)
                                feedback_texto = f"ACESSO NEGADO\n{nome}\n{mensagem}"
                                
                                print(f"\n[NEGADO] {mensagem}\n")
                                mostrar_feedback(frame, feedback_texto, cor_final, duracao=5)
                            
                            atualizar_cooldown(client_id)
                            reconhecimentos_validos[client_id] = 0
                        else:
                            tempo_restante = COOLDOWN_SEGUNDOS - (time.time() - ultimos_reconhecimentos[client_id])
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (128, 128, 128), 2)
                            cv2.putText(frame, f"Aguarde {tempo_restante:.0f}s", (x, y-10),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
                    else:
                        cv2.rectangle(frame, (x, y), (x+w, y+h), cor, 2)
                        cv2.putText(frame, f"{nome} {frames}/{FRAMES_MINIMOS}",
                                   (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)
                else:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), cor, 2)
                    cv2.putText(frame, f"Desconhecido ({confidence:.0f})", (x, y-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)
            
            mostrar_feedback(frame, None, None)
            
            cv2.putText(frame, 'Pressione Q para sair', (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow('Reconhecimento Facial - Academia', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    except KeyboardInterrupt:
        print("\n[INFO] Interrompido")
    
    finally:
        cam.release()
        cv2.destroyAllWindows()
        print("\n[INFO] Camera fechada\n")

if __name__ == '__main__':
    reconhecimento_facial()