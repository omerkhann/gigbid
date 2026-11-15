<template>
  <div class="property-card">
    <img :src="property.image" alt="Property image" />
    <h2>{{ property.title }}</h2>
    <p>{{ property.price | currency }}</p>
    <button @click="viewDetails">View Details</button>
  </div>
</template>

<script>
export default {
  name: 'PropertyCard',
  props: {
    property: {
      type: Object,
      required: true
    }
  },
  methods: {
    viewDetails() {
      this.$emit('select', this.property.id)
    }
  },
  filters: {
    currency(value) {
      return `$${Number(value).toLocaleString()}`
    }
  }
}
</script>

<style scoped>
.property-card { border: 1px solid #ddd; padding: 16px; }
.property-card img { width: 100%; height: auto; }
.property-card h2 { margin: 8px 0; }
.property-card button { background: #007bff; color: #fff; }
</style>
