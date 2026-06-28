const { getTodayExcerpt } = require('../../utils/excerpts')

Page({
  data: {
    loading: true,
    excerpt: null,
    error: ''
  },

  onLoad() {
    this.loadExcerpt()
  },

  async loadExcerpt() {
    this.setData({ loading: true, error: '' })
    try {
      const excerpt = await getTodayExcerpt()
      this.setData({ excerpt, loading: false })
    } catch (error) {
      this.setData({ error: '暂时无法加载今日文摘', loading: false })
    }
  }
})
