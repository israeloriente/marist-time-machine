<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import FaceThumb from "@/components/FaceThumb.vue";
import {
  suggestionsApi,
  type NameVote,
  type TargetWithSuggestions,
} from "@/services/api";
import { useNotifyStore } from "@/stores/notify";

const notify = useNotifyStore();

const items = ref<TargetWithSuggestions[]>([]);
const loading = ref(true);

async function load() {
  loading.value = true;
  try {
    items.value = await suggestionsApi.pendingByTarget();
  } finally {
    loading.value = false;
  }
}

async function approveVote(target: TargetWithSuggestions, vote: NameVote) {
  const final = await notify.prompt({
    title: "Aprovar sugestão",
    message: "Aprovar com qual nome?",
    defaultValue: vote.suggested_name,
    placeholder: "Nome completo",
    confirmLabel: "Aprovar",
    required: true,
  });
  if (final === null) return;
  try {
    await suggestionsApi.approve(vote.suggestion_id, {
      final_name: final || undefined,
      final_graduation_year: vote.suggested_graduation_year ?? null,
      final_class_letter: vote.suggested_class_letter ?? null,
    });
    await load();
  } catch (e) {
    notify.error("Erro ao aprovar sugestão", e);
  }
  void target;
}

async function rejectVote(target: TargetWithSuggestions, vote: NameVote) {
  const ok = await notify.confirm({
    title: "Rejeitar sugestão?",
    message: `"${vote.suggested_name}"`,
    confirmLabel: "Rejeitar",
  });
  if (!ok) return;
  try {
    await suggestionsApi.reject(vote.suggestion_id);
    target.names = target.names.filter((v) => v.suggestion_id !== vote.suggestion_id);
    if (!target.names.length) items.value = items.value.filter((t) => t !== target);
  } catch (e) {
    notify.error("Erro ao rejeitar sugestão", e);
  }
}

onMounted(load);
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Sugestões pendentes</h1>
      <p class="muted">Nomes propostos por usuários, esperando sua aprovação.</p>
    </div>
  </header>

  <p v-if="loading && !items.length" class="muted">Carregando…</p>
  <p v-else-if="!items.length" class="muted">🎉 Nenhuma sugestão pendente.</p>

  <ul v-else class="sugg-cards">
    <li v-for="t in items" :key="(t.person_id ?? t.face_id) as string" class="sugg-card">
      <div class="sugg-card-head">
        <FaceThumb
          v-if="t.thumb_signed_url && t.thumb_bbox"
          :src="t.thumb_signed_url"
          :bbox="t.thumb_bbox"
          :size="80"
          :padding="0.3"
        />
        <div v-else class="thumb-placeholder">?</div>

        <div class="sugg-card-info">
          <strong>
            <template v-if="t.person_id">
              {{ t.face_count }} {{ t.face_count === 1 ? "foto" : "fotos" }}
            </template>
            <template v-else>Rosto avulso</template>
          </strong>
          <span class="muted small">
            {{ t.names.length }} {{ t.names.length === 1 ? "nome sugerido" : "nomes sugeridos" }}
            <template v-if="!t.person_id"> · {{ (t.detection_score * 100).toFixed(0) }}% certeza</template>
          </span>
          <RouterLink
            v-if="t.person_id"
            :to="{ name: 'person', params: { id: t.person_id } }"
            class="muted small link"
          >ver pessoa →</RouterLink>
        </div>
      </div>

      <ul class="vote-list">
        <li v-for="v in t.names" :key="v.suggestion_id" class="vote-row">
          <div class="vote-name">
            <strong>{{ v.suggested_name }}</strong>
            <div class="vote-meta">
              <span v-if="v.suggested_graduation_year" class="tag tag-year">
                {{ v.suggested_graduation_year }}
              </span>
              <span v-if="v.suggested_class_letter" class="tag tag-class">
                {{ v.suggested_class_letter }}
              </span>
              <span class="muted small">
                {{ v.vote_count }} {{ v.vote_count === 1 ? "voto" : "votos" }}
              </span>
            </div>
          </div>
          <div class="vote-ops">
            <button class="button small" @click="approveVote(t, v)">Aprovar</button>
            <button class="button small secondary" @click="rejectVote(t, v)">Rejeitar</button>
          </div>
        </li>
      </ul>
    </li>
  </ul>
</template>

<style scoped>
.page-header { margin-bottom: 1.25rem; }
.page-header h1 { margin: 0; }
.page-header p { margin: 0.2rem 0 0; }

.sugg-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.sugg-card {
  padding: 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.sugg-card-head {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding-bottom: 0.7rem;
  border-bottom: 1px solid var(--border);
}
.sugg-card-info { display: flex; flex-direction: column; gap: 0.2rem; min-width: 0; flex: 1; }
.sugg-card-info strong { color: var(--marista-navy); }
.link { text-decoration: none; color: var(--marista-blue); }

.thumb-placeholder {
  width: 80px; height: 80px;
  border-radius: 8px;
  background: var(--surface-strong);
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); font-size: 1.5rem;
}

.vote-list {
  list-style: none; padding: 0;
  margin: 0.7rem 0 0;
  display: flex; flex-direction: column; gap: 0.4rem;
}
.vote-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.55rem 0.75rem;
  background: rgba(247, 201, 72, 0.08);
  border: 1px solid rgba(247, 201, 72, 0.22);
  border-radius: 8px;
  flex-wrap: wrap;
}
.vote-name { display: flex; flex-direction: column; min-width: 0; gap: 0.2rem; }
.vote-name strong { color: var(--marista-navy); }
.vote-meta { display: flex; gap: 0.3rem; align-items: center; flex-wrap: wrap; }
.tag {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 99px;
  letter-spacing: 0.02em;
}
.tag-year { background: rgba(14, 109, 194, 0.12); color: var(--marista-blue); }
.tag-class { background: rgba(247, 201, 72, 0.22); color: #8a6913; }
.vote-ops { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.button.small {
  min-height: 32px;
  padding: 0.3rem 0.7rem;
  font-size: 0.85rem;
}
.small { font-size: 0.78rem; }
</style>
