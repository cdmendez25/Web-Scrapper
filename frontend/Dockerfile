# syntax=docker/dockerfile:1

# El frontend es HTML suelto: no hay build ni dependencias, asi que no aporta
# nada un multi-stage. Solo se sirve el estatico con nginx.
#
# Se usa la variante "unprivileged" de nginx porque corre como usuario 101
# (nginx) en vez de root y escucha en el 8080 sin necesidad de parches.
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY index.html /usr/share/nginx/html/index.html

EXPOSE 8080
