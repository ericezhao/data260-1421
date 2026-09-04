FROM nginx:alpine
RUN rm -rf /usr/share/nginx/html/*

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY ["web_application/web_app.html", "/usr/share/nginx/html/index.html"]
COPY web_application/styles.css /usr/share/nginx/html/styles.css
COPY web_application/app.js /usr/share/nginx/html/app.js

EXPOSE 8521

CMD ["nginx", "-g", "daemon off;"]
