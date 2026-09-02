FROM nginx:alpine
RUN rm -rf /usr/share/nginx/html/*

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY ["HW1-{Eric Zhao}.html", "/usr/share/nginx/html/index.html"]
COPY styles.css /usr/share/nginx/html/styles.css
COPY app.js /usr/share/nginx/html/app.js

EXPOSE 8521

CMD ["nginx", "-g", "daemon off;"]
