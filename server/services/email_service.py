import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_FROM, EMAIL_FROM_PASSWORD

def send_email(subject: str, body: str, to_email: str):
    from_email = EMAIL_FROM  # Seu e-mail de envio
    from_password = EMAIL_FROM_PASSWORD  # Senha do e-mail (pode ser uma senha de app se for Gmail)

    try:
        # Configurar o servidor SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)  # Para Gmail
        server.starttls()
        server.login(from_email, from_password)

        # Criar o e-mail
        message = MIMEMultipart()
        message["From"] = from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Enviar o e-mail
        server.sendmail(from_email, to_email, message.as_string())
        server.quit()
        print(f"E-mail enviado para {to_email}")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
