<script setup lang="ts">
import { RouterLink } from "vue-router";
import { useResultsStore } from "@/stores/results";

const results = useResultsStore();
</script>

<template>
  <section class="card">
    <div style="display: flex; justify-content: space-between; align-items: baseline; gap: 1rem">
      <h2>Resultados</h2>
      <RouterLink to="/capture" class="muted">Tentar de novo</RouterLink>
    </div>

    <p v-if="!results.data" class="muted">Nenhuma busca feita ainda.</p>
    <template v-else>
      <p class="muted">
        {{ results.data.photos.length }} fotos encontradas
        <template v-if="results.data.person_id">
          — pessoa identificada
        </template>
      </p>

      <div v-if="!results.data.photos.length" class="muted" style="margin-top: 1rem">
        Não achamos correspondências na base. Tente outra foto com melhor iluminação.
      </div>

      <div class="grid" style="margin-top: 1rem">
        <a
          v-for="p in results.data.photos"
          :key="p.photo_id"
          :href="p.signed_url"
          target="_blank"
          rel="noopener"
          :title="`distância ${p.distance.toFixed(3)}`"
        >
          <img :src="p.signed_url" :alt="`Foto ${p.photo_id}`" loading="lazy" />
        </a>
      </div>
    </template>
  </section>
</template>
