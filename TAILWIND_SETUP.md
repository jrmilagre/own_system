# Configuração do Tailwind CSS

Este projeto usa Tailwind CSS para estilização. Para compilar o CSS, siga os passos abaixo:

## Instalação

1. Instale o Node.js (se ainda não tiver): https://nodejs.org/

2. Instale as dependências:
```bash
npm install
```

## Compilação

Para compilar o CSS uma vez:
```bash
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css
```

Para compilar em modo watch (recompila automaticamente ao salvar):
```bash
npm run build-css
```

## Estrutura

- `static/css/input.css` - Arquivo de entrada com diretivas do Tailwind
- `static/css/output.css` - Arquivo compilado (gerado automaticamente)
- `tailwind.config.js` - Configuração do Tailwind
- `package.json` - Dependências do Node.js

## Nota

O arquivo `output.css` deve ser commitado no repositório para que o sistema funcione sem precisar compilar localmente.
