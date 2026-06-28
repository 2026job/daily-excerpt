const db = wx.cloud.database()

async function getTodayExcerpt() {
  const result = await db.collection('excerpts')
    .where({ status: 'published' })
    .orderBy('date', 'desc')
    .limit(1)
    .get()
  return result.data[0] || null
}

async function getHistoryExcerpts(limit = 30) {
  const result = await db.collection('excerpts')
    .where({ status: 'published' })
    .orderBy('date', 'desc')
    .limit(limit)
    .get()
  return result.data
}

async function getExcerptById(id) {
  const result = await db.collection('excerpts').doc(id).get()
  return result.data
}

module.exports = {
  getTodayExcerpt,
  getHistoryExcerpts,
  getExcerptById
}
