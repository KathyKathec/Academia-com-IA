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

# ✅ THRESHOLDS AJUSTADOS
CONFIDENCE_EXCELLENT = 60
CONFIDENCE_GOOD = 80
CONFIDENCE_ACCEPTABLE = 100

# CONTROLE ANTI-LOOP
COOLDOWN_SEGUNDOS = 5
ultimos_reconhecimentos = {}

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
        cliente = Cliente.objects.get(pk=cliente_id)
        
        if not cliente.status:
            return False, "Cliente INATIVO", 0
        
        plano_ativo = ClientePlano.objects.filter(cliente=cliente, ativo=True).first()
        
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
        return False, "ERRO AO VERIFICAR", 0

def registrar_presenca(cliente_id):
    try:
        cliente = Cliente.objects.get(pk=cliente_id)
        hoje = date.today()
        
        ja_registrado = Presenca.objects.filter(cliente=cliente, data=hoje).exists()
        
        if ja_registrado:
            print(f"[INFO] {cliente.nome} ja registrou presenca hoje")
            return False
        
        Presenca.objects.create(cliente=cliente, tipo='facial', usuario=None)
        print(f"[OK] Presenca registrada: {cliente.nome}")
        return True
        
    except Exception as e:
        print(f"[ERRO] Falha ao registrar presenca: {e}")
        return False

def pre_processar_face(face_roi):
    """Apenas redimensiona - igual ao treino"""
    return cv2.resize(face_roi, (200, 200))

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
    
    reconhecimentos_validos = {}
    FRAMES_MINIMOS = 2
    
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
            
            for (x, y, w, h) in faces:
                face_roi = gray[y:y+h, x:x+w]
                face_processed = pre_processar_face(face_roi)
                
                client_id, confidence = recognizer.predict(face_processed)
                
                #  IGNORA ID -1
                if client_id == -1 or confidence > 10000:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (128, 128, 128), 1)
                    continue
                
                # Determina qualidade
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
                
                print(f"[DETECT] ID: {client_id} | Conf: {confidence:.1f} | {qualidade}")
                
                #  BUSCA NOME DO CLIENTE LOGO NO INÍCIO
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
                    
                    print(f"         Frames validos: {frames}/{FRAMES_MINIMOS}")
                    
                    if frames >= FRAMES_MINIMOS:
                        if pode_reconhecer_novamente(client_id):
                            try:
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
                                reconhecimentos_validos[client_id] = 0
                                
                                cv2.rectangle(frame, (x, y), (x+w, y+h), cor_final, 3)
                                cv2.putText(frame, nome, (x, y-40),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_final, 2)
                                cv2.putText(frame, mensagem, (x, y-10),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_final, 2)
                            
                            except Exception as e:
                                print(f"[ERRO] Excecao: {e}")
                                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                                cv2.putText(frame, "ERRO", (x, y-10),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        else:
                            tempo_restante = COOLDOWN_SEGUNDOS - (time.time() - ultimos_reconhecimentos[client_id])
                            print(f"         Cooldown: {tempo_restante:.1f}s")
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (128, 128, 128), 2)
                            cv2.putText(frame, "AGUARDE...", (x, y-10),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
                    else:
                 
                        cv2.rectangle(frame, (x, y), (x+w, y+h), cor, 2)
                        cv2.putText(frame, f"{nome} {frames}/{FRAMES_MINIMOS}",
                                   (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)
                else:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), cor, 2)
                    cv2.putText(frame, f"DESCONHECIDO ({confidence:.0f})", (x, y-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)
            
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