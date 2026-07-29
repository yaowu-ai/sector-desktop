import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Input,
  Modal,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ClipboardPaste, Plus, RefreshCw, Save, Trash2, Undo2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageHeader } from '../components/PageHeader'
import { usePlatformContext } from '../app/PlatformContext'
import { loadCommentPools, saveCommentPools } from '../services/api'
import type { CommentPool, CommentPoolsSnapshot, SaveCommentPoolsResult } from '../services/types'

type PoolKey = 'general' | 'brand'

interface CommentRow {
  id: string
  text: string
}

interface PoolDraft {
  rows: CommentRow[]
  path: string
  commentLines: number
  blankLines: number
  duplicates: string[]
}

const POOL_LABELS: Record<PoolKey, string> = {
  general: '通用评论池',
  brand: '品牌评论池',
}

export function CommentPoolPage() {
  const { currentPlatform, currentPlatformDefinition } = usePlatformContext()
  const [snapshot, setSnapshot] = useState<CommentPoolsSnapshot | null>(null)
  const [drafts, setDrafts] = useState<Record<PoolKey, PoolDraft>>({
    general: emptyDraft(),
    brand: emptyDraft(),
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveWarnings, setSaveWarnings] = useState<string[]>([])
  const [pastePool, setPastePool] = useState<PoolKey | null>(null)
  const [pasteText, setPasteText] = useState('')
  const [tablePages, setTablePages] = useState<Record<PoolKey, number>>({
    general: 1,
    brand: 1,
  })

  const dirty = useMemo(() => {
    if (!snapshot) {
      return false
    }
    return (
      rowsToText(drafts.general.rows) !== commentsToText(snapshot.general.comments) ||
      rowsToText(drafts.brand.rows) !== commentsToText(snapshot.brand.comments)
    )
  }, [drafts, snapshot])

  const duplicateWarnings = useMemo(
    () => ({
      general: findDuplicateComments(drafts.general.rows),
      brand: findDuplicateComments(drafts.brand.rows),
    }),
    [drafts],
  )

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const nextSnapshot = await loadCommentPools(currentPlatform)
      setSnapshot(nextSnapshot)
      setDrafts(snapshotToDrafts(nextSnapshot))
      setSaveWarnings([])
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setLoading(false)
    }
  }, [currentPlatform])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const save = async () => {
    setSaving(true)
    try {
      const result = await saveCommentPools({
        platform: currentPlatform,
        generalText: rowsToText(drafts.general.rows),
        brandText: rowsToText(drafts.brand.rows),
      })
      applySaveResult(result)
      message.success('评论素材已保存')
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setSaving(false)
    }
  }

  const applySaveResult = (result: SaveCommentPoolsResult) => {
    const nextSnapshot = {
      platform: currentPlatform,
      general: result.general,
      brand: result.brand,
    }
    setSnapshot(nextSnapshot)
    setDrafts(snapshotToDrafts(nextSnapshot))
    setSaveWarnings(result.warnings)
  }

  const restore = () => {
    if (!dirty) {
      void refresh()
      return
    }
    Modal.confirm({
      title: '恢复上次保存',
      content: '当前未保存修改会被磁盘中的评论池覆盖。',
      okText: '恢复',
      cancelText: '取消',
      onOk: () => refresh(),
    })
  }

  const addRow = (poolKey: PoolKey) => {
    setTablePages((current) => ({ ...current, [poolKey]: 1 }))
    setDrafts((current) => ({
      ...current,
      [poolKey]: {
        ...current[poolKey],
        rows: [createRow(''), ...current[poolKey].rows],
      },
    }))
  }

  const updateRow = (poolKey: PoolKey, rowId: string, text: string) => {
    setDrafts((current) => ({
      ...current,
      [poolKey]: {
        ...current[poolKey],
        rows: current[poolKey].rows.map((row) => (row.id === rowId ? { ...row, text } : row)),
      },
    }))
  }

  const deleteRow = (poolKey: PoolKey, rowId: string) => {
    setDrafts((current) => ({
      ...current,
      [poolKey]: {
        ...current[poolKey],
        rows: current[poolKey].rows.filter((row) => row.id !== rowId),
      },
    }))
  }

  const openPaste = (poolKey: PoolKey) => {
    setPastePool(poolKey)
    setPasteText('')
  }

  const applyPaste = () => {
    if (!pastePool) {
      return
    }
    const parsed = parseCommentLines(pasteText)
    if (parsed.comments.length === 0) {
      message.warning('没有可添加的有效评论')
      return
    }
    setDrafts((current) => ({
      ...current,
      [pastePool]: {
        ...current[pastePool],
        rows: [...current[pastePool].rows, ...parsed.comments.map(createRow)],
      },
    }))
    setPastePool(null)
    setPasteText('')
    message.success(`已添加 ${parsed.comments.length} 条评论`)
  }

  return (
    <>
      <PageHeader
        title="评论素材"
        description={`维护 ${currentPlatformDefinition.localeName} 通用评论池和品牌评论池；当前兼容写入旧全局评论文件。`}
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={() => void refresh()}>
              刷新
            </Button>
            <Button icon={<Undo2 size={16} />} disabled={!dirty} onClick={restore}>
              恢复上次保存
            </Button>
            <Button type="primary" icon={<Save size={16} />} loading={saving} disabled={!dirty} onClick={() => void save()}>
              保存
            </Button>
          </Space>
        }
      />

      <Spin spinning={loading}>
        <Space direction="vertical" size={16} className="full-width">
          {saveWarnings.length ? (
            <Alert
              type="warning"
              showIcon
              message="保存提示"
              description={
                <Space direction="vertical" size={2}>
                  {saveWarnings.map((warning) => (
                    <Typography.Text key={warning}>{warning}</Typography.Text>
                  ))}
                </Space>
              }
            />
          ) : null}

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <CommentPoolEditor
                poolKey="general"
                draft={drafts.general}
                tablePage={tablePages.general}
                duplicateComments={duplicateWarnings.general}
                onAdd={addRow}
                onPaste={openPaste}
                onPageChange={(page) => setTablePages((current) => ({ ...current, general: page }))}
                onDelete={deleteRow}
                onUpdate={updateRow}
              />
            </Col>
            <Col xs={24} xl={12}>
              <CommentPoolEditor
                poolKey="brand"
                draft={drafts.brand}
                tablePage={tablePages.brand}
                duplicateComments={duplicateWarnings.brand}
                onAdd={addRow}
                onPaste={openPaste}
                onPageChange={(page) => setTablePages((current) => ({ ...current, brand: page }))}
                onDelete={deleteRow}
                onUpdate={updateRow}
              />
            </Col>
          </Row>
        </Space>
      </Spin>

      <Modal
        title={pastePool ? `${POOL_LABELS[pastePool]}批量粘贴` : '批量粘贴'}
        open={Boolean(pastePool)}
        okText="添加"
        cancelText="取消"
        width={720}
        onCancel={() => setPastePool(null)}
        onOk={applyPaste}
      >
        <Input.TextArea
          value={pasteText}
          onChange={(event) => setPasteText(event.target.value)}
          rows={12}
          placeholder="每行一条评论；空行和 # 开头行会忽略"
        />
        <PasteSummary text={pasteText} />
      </Modal>
    </>
  )
}

function CommentPoolEditor({
  poolKey,
  draft,
  tablePage,
  duplicateComments,
  onAdd,
  onPaste,
  onPageChange,
  onDelete,
  onUpdate,
}: {
  poolKey: PoolKey
  draft: PoolDraft
  tablePage: number
  duplicateComments: string[]
  onAdd: (poolKey: PoolKey) => void
  onPaste: (poolKey: PoolKey) => void
  onPageChange: (page: number) => void
  onDelete: (poolKey: PoolKey, rowId: string) => void
  onUpdate: (poolKey: PoolKey, rowId: string, text: string) => void
}) {
  const columns: ColumnsType<CommentRow> = [
    {
      title: '#',
      width: 58,
      render: (_, __, index) => index + 1,
    },
    {
      title: '评论',
      dataIndex: 'text',
      render: (value: string, row) => (
        <Input.TextArea
          autoSize={{ minRows: 1, maxRows: 3 }}
          value={value}
          status={isIgnoredLine(value) ? 'warning' : undefined}
          onChange={(event) => onUpdate(poolKey, row.id, event.target.value)}
        />
      ),
    },
    {
      title: '操作',
      width: 92,
      render: (_, row) => (
        <Button danger icon={<Trash2 size={15} />} onClick={() => onDelete(poolKey, row.id)}>
          删除
        </Button>
      ),
    },
  ]

  return (
    <Card
      title={POOL_LABELS[poolKey]}
      extra={
        <Space>
          <Button icon={<ClipboardPaste size={16} />} onClick={() => onPaste(poolKey)}>
            批量粘贴
          </Button>
          <Button type="primary" icon={<Plus size={16} />} onClick={() => onAdd(poolKey)}>
            新增
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" size={12} className="full-width">
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="有效评论">{activeCommentCount(draft.rows)}</Descriptions.Item>
          <Descriptions.Item label="重复项">{duplicateComments.length}</Descriptions.Item>
          <Descriptions.Item label="原注释行">{draft.commentLines}</Descriptions.Item>
          <Descriptions.Item label="原空行">{draft.blankLines}</Descriptions.Item>
          <Descriptions.Item label="素材库" span={2}>
            <Tag color={draft.path ? 'green' : 'default'}>{draft.path ? '已加载' : '未加载'}</Tag>
          </Descriptions.Item>
        </Descriptions>

        {duplicateComments.length ? (
          <Alert
            type="warning"
            showIcon
            message={`${POOL_LABELS[poolKey]}存在重复评论`}
            description={duplicateComments.slice(0, 5).join(' / ')}
          />
        ) : null}

        <Table
          rowKey="id"
          columns={columns}
          dataSource={draft.rows}
          pagination={{
            current: tablePage,
            pageSize: 10,
            showSizeChanger: true,
            onChange: onPageChange,
          }}
        />
      </Space>
    </Card>
  )
}

function PasteSummary({ text }: { text: string }) {
  const parsed = parseCommentLines(text)
  if (!text.trim()) {
    return null
  }
  return (
    <Space wrap style={{ marginTop: 12 }}>
      <Tag color="green">有效 {parsed.comments.length}</Tag>
      <Tag>空行 {parsed.blankLines}</Tag>
      <Tag>注释 {parsed.commentLines}</Tag>
      {parsed.duplicates.length ? <Tag color="gold">重复 {parsed.duplicates.length}</Tag> : null}
    </Space>
  )
}

function snapshotToDrafts(snapshot: Pick<CommentPoolsSnapshot, 'general' | 'brand'>): Record<PoolKey, PoolDraft> {
  return {
    general: poolToDraft(snapshot.general),
    brand: poolToDraft(snapshot.brand),
  }
}

function poolToDraft(pool: CommentPool): PoolDraft {
  return {
    rows: pool.comments.map(createRow),
    path: pool.path,
    commentLines: pool.commentLines,
    blankLines: pool.blankLines,
    duplicates: pool.duplicates,
  }
}

function parseCommentLines(text: string) {
  const comments: string[] = []
  const duplicates: string[] = []
  const seen = new Set<string>()
  let blankLines = 0
  let commentLines = 0

  for (const line of text.split(/\r?\n/)) {
    const value = line.trim()
    if (!value) {
      blankLines += 1
      continue
    }
    if (value.startsWith('#')) {
      commentLines += 1
      continue
    }
    const key = value.toLowerCase()
    if (seen.has(key)) {
      duplicates.push(value)
      continue
    }
    seen.add(key)
    comments.push(value)
  }

  return { comments, duplicates, blankLines, commentLines }
}

function findDuplicateComments(rows: CommentRow[]) {
  return parseCommentLines(rowsToText(rows)).duplicates
}

function rowsToText(rows: CommentRow[]) {
  return rows.map((row) => row.text).join('\n')
}

function commentsToText(comments: string[]) {
  return comments.join('\n')
}

function activeCommentCount(rows: CommentRow[]) {
  return parseCommentLines(rowsToText(rows)).comments.length
}

function isIgnoredLine(value: string) {
  const normalized = value.trim()
  return normalized.length === 0 || normalized.startsWith('#')
}

function createRow(text: string): CommentRow {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    text,
  }
}

function emptyDraft(): PoolDraft {
  return {
    rows: [],
    path: '',
    commentLines: 0,
    blankLines: 0,
    duplicates: [],
  }
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
