import os
import sys
import cv2
import numpy as np
from datetime import date, datetime
from pathlib import Path

# Garantir raiz do projeto no PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia.settings')
import django
django.setup()

from gym.models import Cliente, Presenca, ClientePlano
from django.contrib.auth.models import User

def verificar_acesso_cliente(cliente_id):
    """
    Verifica se o cliente tem plano ativo e válido
    Retorna (pode_entrar, mensagem, dias_restantes)
    """
    try:
        cliente = Cliente.objects.get(pk=cliente_id)
        
        # Verifica se cliente está ativo
        if not cliente.status:
            return False, "Cliente INATIVO", 0
        
        # Busca plano ativo
        plano_ativo = ClientePlano.objects.filter(
            cliente=cliente,
            ativo=True
        ).first()
        
        if not plano_ativo:
            return False, "SEM PLANO ATIVO", 0
        
        # Verifica vencimento
        hoje = date.today()
        if plano_ativo.data_fim < hoje:
            dias_vencido = (hoje - plano_ativo.data_fim).days
            return False, f"PLANO VENCIDO ({dias_vencido} dias)", -dias_vencido
        
        # Plano válido
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
        
        # Verifica se já registrou hoje
        ja_registrado = Presenca.objects.filter(
            cliente=cliente,
            data=hoje
        ).exists()
        
        if ja_registrado:
            print(f"[INFO] {cliente.nome} já registrou presença hoje")
            return False
        
        # Cria registro de presença
        Presenca.objects.create(
            cliente=cliente,
            tipo='facial',
            usuario=None  # Sistema automático
        )
        
        print(f"[✓] Presença registrada: {cliente.nome}")
        return True
        
    except Exception as e:
        print(f"[ERRO] Falha ao registrar presença: {e}")
        return False

def reconhecimento_facial():
    """Executa reconhecimento facial com validação de acesso"""
    
    # Caminho do modelo treinado
    trainer_path = Path(__file__).parent / 'trainer.yml'
    
    if not trainer_path.exists():
        print("❌ Modelo não treinado! Execute treina.py primeiro.")
        return
    
    print("\n" + "="*60)
    print("🎥 SISTEMA DE RECONHECIMENTO FACIAL")
    print("="*60)
    print("[INFO] Iniciando câmera...")
    print("[INFO] Pressione 'Q' para sair")
    print("="*60 + "\n")
    
    # Carrega classificador de faces
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_detector = cv2.CascadeClassifier(cascade_path)
    
    # Carrega reconhecedor
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(trainer_path))
    
    # Inicializa câmera
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cam.isOpened():
        print("❌ Erro ao acessar a câmera!")
        return
    
    # Controle de reconhecimento
    ultimo_reconhecido = None
    frames_reconhecido = 0
    FRAMES_NECESSARIOS = 10  # Precisa reconhecer por 10 frames seguidos
    
    try:
        while True:
            ret, frame = cam.read()
            
            if not ret:
                break
            
            # Converte para escala de cinza
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            
            # Detecta faces
            faces = face_detector.detectMultiScale(
                gray,
                scaleFactor=1.3,
                minNeighbors=5,
                minSize=(100, 100)
            )
            
            for (x, y, w, h) in faces:
                # Extrai região da face
                face_roi = gray[y:y+h, x:x+w]
                
                # Reconhece
                client_id, confidence = recognizer.predict(face_roi)
                
                # Confiança (quanto menor, melhor)
                if confidence < 70:  # Limiar de confiança
                    # Cliente reconhecido
                    if ultimo_reconhecido == client_id:
                        frames_reconhecido += 1
                    else:
                        ultimo_reconhecido = client_id
                        frames_reconhecido = 1
                    
                    # Se reconheceu por frames suficientes
                    if frames_reconhecido >= FRAMES_NECESSARIOS:
                        #  VALIDA ACESSO
                        pode_entrar, mensagem, dias = verificar_acesso_cliente(client_id)
                        
                        try:
                            cliente = Cliente.objects.get(pk=client_id)
                            nome = cliente.nome
                        except:
                            nome = f"ID: {client_id}"
                        
                        if pode_entrar:
                            #  ACESSO LIBERADO
                            cor_box = (0, 255, 0)  # Verde
                            cor_texto = (0, 255, 0)
                            
                            # Registra presença
                            registrar_presenca(client_id)
                            
                            print(f"\n✅ ACESSO LIBERADO")
                            print(f"   Cliente: {nome}")
                            print(f"   Status: {mensagem}")
                            if dias > 0:
                                print(f"   Plano válido por mais {dias} dias")
                        else:
                            # ❌ ACESSO NEGADO
                            cor_box = (0, 0, 255)  # Vermelho
                            cor_texto = (0, 0, 255)
                            
                            print(f"\n❌ ACESSO NEGADO")
                            print(f"   Cliente: {nome}")
                            print(f"   Motivo: {mensagem}")
                        
                        # Desenha retângulo
                        cv2.rectangle(frame, (x, y), (x+w, y+h), cor_box, 3)
                        
                        # Mostra nome
                        cv2.putText(frame, nome, (x, y-40),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_texto, 2)
                        
                        # Mostra status
                        cv2.putText(frame, mensagem, (x, y-10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_texto, 2)
                        
                        # Reset contador
                        frames_reconhecido = 0
                        ultimo_reconhecido = None
                    else:
                        # Ainda reconhecendo...
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 0), 2)
                        cv2.putText(frame, 'Reconhecendo...', (x, y-10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                else:
                    # Face não reconhecida
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (128, 128, 128), 2)
                    cv2.putText(frame, 'Desconhecido', (x, y-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
                    
                    ultimo_reconhecido = None
                    frames_reconhecido = 0
            
            # Instruções na tela
            cv2.putText(frame, 'Pressione Q para sair', (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Mostra frame
            cv2.imshow('Reconhecimento Facial - Academia', frame)
            
            # Verifica tecla
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    except KeyboardInterrupt:
        print("\n⚠️  Reconhecimento interrompido")
    
    finally:
        cam.release()
        cv2.destroyAllWindows()
        print("\n[INFO] Câmera fechada")
        print("="*60)

if __name__ == '__main__':
    reconhecimento_facial()