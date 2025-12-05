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

# Garantir raiz do projeto no PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia.settings')
import django
django.setup()

from gym.models import Cliente, Presenca, ClientePlano

CONFIDENCE_EXCELLENT = 70   # Mais tolerante
CONFIDENCE_GOOD = 90
CONFIDENCE_ACCEPTABLE = 110

# CONTROLE ANTI-LOOP
COOLDOWN_SEGUNDOS = 5
ultimos_reconhecimentos = {}

def pode_reconhecer_novamente(client_id):
    """Verifica se passou tempo suficiente desde último reconhecimento"""
    agora = time.time()
    
    if client_id not in ultimos_reconhecimentos:
        return True
    
    tempo_decorrido = agora - ultimos_reconhecimentos[client_id]
    return tempo_decorrido >= COOLDOWN_SEGUNDOS

def atualizar_cooldown(client_id):
    """Atualiza timestamp do último reconhecimento"""
    ultimos_reconhecimentos[client_id] = time.time()

def verificar_acesso_cliente(cliente_id):
    """Verifica se o cliente tem plano ativo e válido"""
    try:
        cliente = Cliente.objects.get(pk=cliente_id)
        
        if not cliente.status:
            return False, "Cliente INATIVO", 0
        
        plano_ativo = ClientePlano.objects.filter(
            cliente=cliente,
            ativo=True
        ).first()
        
        if not plano_ativo:
            return False, "SEM PLANO ATIVO", 0
        
        hoje = date.today()
        if plano_ativo.data_fim < hoje:
            dias_vencido = (hoje - plano_ativo.data_fim).days
            return False, f"PLANO VENCIDO ({dias_vencido} dias)", -dias_vencido
        
        dias_restantes = (plano_ativo.data_fim - hoje).days
        
        if dias_restantes == 0:
            return True, "VENCE HOJE!", 0
        elif dias_restantes <= 3:
            return True, f"Vence em {dias_restantes} dias", dias_restantes
        else:
            return True, "ACESSO LIBERADO", dias_restantes
            
    except Cliente.DoesNotExist:
        return False, "Cliente NAO ENCONTRADO", 0
    except Exception as e:
        print(f"Erro ao verificar acesso: {e}")
        return False, "ERRO AO VERIFICAR", 0

def registrar_presenca(cliente_id):
    """Registra presença do cliente"""
    try:
        cliente = Cliente.objects.get(pk=cliente_id)
        hoje = date.today()
        
        ja_registrado = Presenca.objects.filter(
            cliente=cliente,
            data=hoje
        ).exists()
        
        if ja_registrado:
            print(f"[INFO] {cliente.nome} ja registrou presenca hoje")
            return False
        
        Presenca.objects.create(
            cliente=cliente,
            tipo='facial',
            usuario=None
        )
        
        print(f"[OK] Presenca registrada: {cliente.nome}")
        return True
        
    except Exception as e:
        print(f"[ERRO] Falha ao registrar presenca: {e}")
        return False

def pre_processar_face(face_roi):
    """ APENAS REDIMENSIONA - IGUAL AO TREINO"""
    return cv2.resize(face_roi, (200, 200))

def reconhecimento_facial():
    """Executa reconhecimento facial com validação rigorosa"""
    
    trainer_path = Path(__file__).parent / 'trainer.yml'
    
    if not trainer_path.exists():
        print("ERRO: Modelo nao treinado! Execute treina.py primeiro.")
        return
    
    print("\n" + "="*60)
    print("SISTEMA DE RECONHECIMENTO FACIAL")
    print("="*60)
    print("[INFO] Thresholds configurados:")
    print(f"  Excelente: < {CONFIDENCE_EXCELLENT}")
    print(f"  Bom: < {CONFIDENCE_GOOD}")
    print(f"  Aceitavel: < {CONFIDENCE_ACCEPTABLE}")
    print(f"  Desconhecido: >= {CONFIDENCE_ACCEPTABLE}")
    print(f"[INFO] Cooldown: {COOLDOWN_SEGUNDOS}s entre reconhecimentos")
    print("[INFO] Pressione 'Q' para sair")
    print("="*60 + "\n")
    
    # Carrega classificador e reconhecedor
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_detector = cv2.CascadeClassifier(cascade_path)
    
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(trainer_path))
    
    # Inicializa câmera
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # Mesma resolução da captura
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    if not cam.isOpened():
        print("ERRO: Nao foi possivel acessar a camera!")
        return
    
    reconhecimentos_consecutivos = {}
    FRAMES_MINIMOS = 3  # Reduzido de 5 para 3 (mais rápido)
    
    try:
        frame_count = 0
        
        while True:
            ret, frame = cam.read()
            
            if not ret:
                break
            
            frame_count += 1
            
            # Processa a cada 2 frames (mais rápido que 3)
            if frame_count % 2 != 0:
                cv2.imshow('Reconhecimento Facial - Academia', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue
            
            # Converte para escala de cinza
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Equaliza (como no treinamento)
            gray_eq = cv2.equalizeHist(gray)
            
            # Detecta faces
            faces = face_detector.detectMultiScale(
                gray_eq,
                scaleFactor=1.1,  #  Mesmo do treinamento
                minNeighbors=6,
                minSize=(150, 150),  #  Ajustado
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            if len(faces) == 0:
                reconhecimentos_consecutivos.clear()
            
            for (x, y, w, h) in faces:
                # Extrai ROI da face
                face_roi = gray[y:y+h, x:x+w]
                
                # APLICA MESMO PRÉ-PROCESSAMENTO DO TREINO
                face_processed = pre_processar_face(face_roi)
                
                # Reconhece
                client_id, confidence = recognizer.predict(face_processed)
                
                # Determina qualidade
                if confidence < CONFIDENCE_EXCELLENT:
                    qualidade = "EXCELENTE"
                    cor = (0, 255, 0)
                    nivel_confianca = 3
                elif confidence < CONFIDENCE_GOOD:
                    qualidade = "BOM"
                    cor = (0, 255, 255)
                    nivel_confianca = 2
                elif confidence < CONFIDENCE_ACCEPTABLE:
                    qualidade = "ACEITAVEL"
                    cor = (0, 165, 255)
                    nivel_confianca = 1
                else:
                    qualidade = "DESCONHECIDO"
                    cor = (0, 0, 255)
                    nivel_confianca = 0
                
                print(f"[DETECT] ID: {client_id} | Confianca: {confidence:.1f} | {qualidade}")
                
                if nivel_confianca > 0:
                    if client_id not in reconhecimentos_consecutivos:
                        reconhecimentos_consecutivos[client_id] = 0
                    
                    reconhecimentos_consecutivos[client_id] += 1
                    frames_consecutivos = reconhecimentos_consecutivos[client_id]
                    
                    print(f"         Frames: {frames_consecutivos}/{FRAMES_MINIMOS}")
                    
                    if frames_consecutivos >= FRAMES_MINIMOS:
                        if pode_reconhecer_novamente(client_id):
                            try:
                                cliente = Cliente.objects.get(id=client_id)
                                nome = cliente.nome
                                
                                pode_entrar, mensagem, dias = verificar_acesso_cliente(client_id)
                                
                                if pode_entrar:
                                    cor_final = (0, 255, 0)
                                    registrar_presenca(client_id)
                                    print(f"\n[OK] ACESSO LIBERADO - {nome}")
                                    print(f"     {mensagem}\n")
                                else:
                                    cor_final = (0, 0, 255)
                                    print(f"\n[ERRO] ACESSO NEGADO - {nome}")
                                    print(f"       {mensagem}\n")
                                
                                atualizar_cooldown(client_id)
                                reconhecimentos_consecutivos[client_id] = 0
                                
                                cv2.rectangle(frame, (x, y), (x+w, y+h), cor_final, 3)
                                cv2.putText(frame, nome, (x, y-40),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_final, 2)
                                cv2.putText(frame, mensagem, (x, y-10),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_final, 2)
                            
                            except Cliente.DoesNotExist:
                                print(f"[ERRO] ID {client_id} nao encontrado no banco")
                                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                                cv2.putText(frame, "ID INVALIDO", (x, y-10),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        else:
                            tempo_restante = COOLDOWN_SEGUNDOS - (time.time() - ultimos_reconhecimentos[client_id])
                            print(f"         Cooldown: {tempo_restante:.1f}s")
                            
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (128, 128, 128), 2)
                            cv2.putText(frame, "AGUARDE...", (x, y-10),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
                    else:
                        cv2.rectangle(frame, (x, y), (x+w, y+h), cor, 2)
                        cv2.putText(frame, f"Validando {frames_consecutivos}/{FRAMES_MINIMOS}",
                                   (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)
                else:
                    reconhecimentos_consecutivos.clear()
                    cv2.rectangle(frame, (x, y), (x+w, y+h), cor, 2)
                    cv2.putText(frame, f"DESCONHECIDO ({confidence:.0f})", (x, y-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)
            
            cv2.putText(frame, 'Pressione Q para sair', (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow('Reconhecimento Facial - Academia', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    except KeyboardInterrupt:
        print("\n[INFO] Reconhecimento interrompido")
    
    finally:
        cam.release()
        cv2.destroyAllWindows()
        print("\n[INFO] Camera fechada")
        print("="*60)

if __name__ == '__main__':
    reconhecimento_facial()