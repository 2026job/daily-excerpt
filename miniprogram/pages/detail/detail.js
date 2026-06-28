const { getExcerptById } = require('../../utils/excerpts')

Page({
  data: {
    loading: true,
    excerpt: null,
    error: ''
  },

  onLoad(options) {
    this.loadDetail(options.id)
  },

  async loadDetail(id) {
    if (!id) {
      this.setData({ loading: false, error: '缺少文摘 ID' })
      return
    }
    try {
      const excerpt = await getExcerptById(id)
      this.setData({ excerpt, loading: false })
    } catch (error) {
      this.setData({ error: '暂时无法加载文摘详情', loading: false })
    }
  }
})
