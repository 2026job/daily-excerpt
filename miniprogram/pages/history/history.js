const { getHistoryExcerpts } = require('../../utils/excerpts')

Page({
  data: {
    loading: true,
    excerpts: [],
    error: ''
  },

  onLoad() {
    this.loadHistory()
  },

  async loadHistory() {
    this.setData({ loading: true, error: '' })
    try {
      const excerpts = await getHistoryExcerpts()
      this.setData({ excerpts, loading: false })
    } catch (error) {
      this.setData({ error: '暂时无法加载历史文摘', loading: false })
    }
  },

  openDetail(event) {
    const id = event.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/detail/detail?id=${id}` })
  }
})
