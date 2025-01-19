from deepface import DeepFace

# Carregar a imagem e fazer o reconhecimento
image_path = "images/io.jpg"
result = DeepFace.represent(image_path, model_name="VGG-Face", detector_backend="opencv")

# Exibir os vetores de embedding gerados para cada rosto detectado
# for face_embedding in result:
#     print(face_embedding)

print(len(result))
