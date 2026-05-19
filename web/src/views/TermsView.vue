<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>

<template>
  <article class="terms">
    <header class="terms-head">
      <span class="kicker">Política</span>
      <h1>Termos de Uso e Política de Privacidade</h1>
      <p class="muted">Última atualização: 19 de maio de 2026</p>
    </header>

    <section>
      <h2>1. O que é a Cápsula do Tempo Marista</h2>
      <p>
        A <strong>Cápsula do Tempo Marista</strong> (“a plataforma”) é uma
        ferramenta comunitária mantida por ex-alunos do Colégio Marista Pio X
        para preservar e compartilhar memórias fotográficas e audiovisuais
        do colégio. A plataforma usa reconhecimento facial para ajudar você a
        encontrar fotos antigas em que aparece.
      </p>
    </section>

    <section>
      <h2>2. Conta e cadastro</h2>
      <p>
        Para usar a plataforma, você cria uma conta com seu e-mail Google e
        informa o seu ano de formatura e turma. Esses dados servem apenas
        para organizar o acervo. Você pode pedir a remoção da sua conta a
        qualquer momento entrando em contato com a administração.
      </p>
    </section>

    <section>
      <h2>3. Responsabilidade pelo conteúdo enviado</h2>
      <p>
        <strong>Cada usuário é o único responsável pelas mídias (fotos e vídeos)
        que envia.</strong> Ao fazer upload, você declara que:
      </p>
      <ul>
        <li>É autor da mídia ou tem autorização para compartilhá-la;</li>
        <li>
          Não envia conteúdo que viole direitos de imagem, direitos autorais
          ou a privacidade de terceiros;
        </li>
        <li>
          Não envia conteúdo ilegal, ofensivo, discriminatório, sexual,
          violento ou que exponha menores de idade de forma inapropriada.
        </li>
      </ul>
      <p>
        Conteúdo enviado em desacordo com esses pontos será removido sem aviso
        prévio. Casos graves poderão ser comunicados às autoridades.
      </p>
    </section>

    <section>
      <h2>4. Limitação de responsabilidade</h2>
      <p>
        <strong>
          Nem os mantenedores da plataforma, nem o Colégio Marista Pio X
          assumem qualquer responsabilidade pelo conteúdo enviado pelos
          usuários.
        </strong>
        A Cápsula do Tempo é uma iniciativa de ex-alunos, hospedada de forma
        independente; o Colégio Marista Pio X não é proprietário, operador
        nem mantenedor da plataforma.
      </p>
      <p>
        A plataforma é fornecida “como está”, sem garantias de disponibilidade,
        integridade dos dados ou continuidade do serviço. Use por sua conta e
        risco.
      </p>
    </section>

    <section>
      <h2>5. Busca por selfie e reconhecimento facial</h2>
      <p>
        Ao tirar uma selfie para buscar fotos antigas, a sua imagem é
        processada para extrair características faciais que servem apenas à
        consulta. <strong>A selfie não é armazenada</strong>; somente os
        vetores numéricos resultantes são comparados com os do acervo, e
        depois descartados.
      </p>
      <p>
        Os rostos detectados nas fotos enviadas <em>são</em> armazenados de
        forma agrupada para permitir que você e outros ex-alunos encontrem
        memórias compartilhadas.
      </p>
    </section>

    <section>
      <h2>6. Como pedir a remoção da sua mídia</h2>
      <p>
        Se você está em uma foto ou vídeo do acervo e gostaria de remover,
        <strong>basta clicar em “Denunciar” na própria mídia</strong>. A
        denúncia chega a um administrador, que avaliará e removerá o
        conteúdo se considerar legítimo. Inclua o motivo (e, se quiser, um
        contato para retorno) ao denunciar.
      </p>
      <p>
        Você também pode pedir a remoção em massa de qualquer foto onde
        apareça entrando em contato direto com a administração da plataforma.
      </p>
    </section>

    <section>
      <h2>7. Dados que coletamos</h2>
      <ul>
        <li>Seu e-mail (vindo do Google);</li>
        <li>Seu ano de formatura e turma;</li>
        <li>As fotos e vídeos que você envia;</li>
        <li>
          Os vetores faciais (embeddings) extraídos das fotos e vídeos do
          acervo;
        </li>
        <li>
          Denúncias que você faz, para fins de moderação e auditoria.
        </li>
      </ul>
      <p>
        Não vendemos, alugamos ou compartilhamos esses dados com terceiros.
      </p>
    </section>

    <section>
      <h2>8. Alterações</h2>
      <p>
        Estes termos podem ser atualizados. Mudanças significativas serão
        notificadas no próximo login e poderão exigir nova aceitação.
      </p>
    </section>

    <p class="footer-actions">
      <RouterLink to="/" class="button secondary">Voltar</RouterLink>
    </p>
  </article>
</template>

<style scoped>
.terms {
  max-width: 760px;
  margin: 1rem auto 3rem;
  padding: 1.5rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  color: var(--text);
  line-height: 1.6;
}
.terms-head {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}
.kicker {
  display: inline-block;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  font-size: 0.7rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.85rem;
}
.terms h1 {
  margin: 0 0 0.35rem;
  color: var(--marista-navy);
  font-size: 1.7rem;
}
.terms h2 {
  margin: 1.5rem 0 0.5rem;
  color: var(--marista-navy);
  font-size: 1.1rem;
}
.terms p { margin: 0.45rem 0; }
.terms ul { padding-left: 1.2rem; }
.terms li { margin: 0.25rem 0; }
.footer-actions { text-align: center; margin-top: 2rem; }
</style>
