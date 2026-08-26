import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ClipboardPaste, KeyRound, PlugZap, Plus, RefreshCw, Save, Sparkles, Trash2, Undo2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageHeader } from '../components/PageHeader'
import { useDesktopAuth } from '../app/DesktopAuthContext'
import { usePlatformContext } from '../app/PlatformContext'
import {
  deleteAiCommentApiKey,
  getAiCommentApiKeyStatus,
  loadAiCommentSettings,
  loadCommentPools,
  previewAiComment,
  saveAiCommentApiKey,
  saveAiCommentSettings,
  saveCommentPools,
  testAiCommentConnection,
} from '../services/api'
import { desktopLicenseAllowsAiComment } from '../services/desktopApi'
import type {
  AiCommentApiKeyStatus,
  AiCommentGenerationResult,
  AiCommentSettings,
  CommentPool,
  CommentPoolsSnapshot,
  SaveCommentPoolsResult,
} from '../services/types'

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

const DEFAULT_AI_COMMENT_SETTINGS: AiCommentSettings = {
  enabled: false,
  provider: 'kimi_moonshot',
  baseUrl: 'https://api.moonshot.cn/v1',
  model: 'kimi-k2.6',
  timeoutSeconds: 5,
  maxCommentLength: 80,
  fallbackToPool: true,
  language: 'auto',
  blockedWords: [],
}

export function CommentPoolPage() {
  const { currentPlatform, currentPlatformDefinition } = usePlatformContext()
  const { license } = useDesktopAuth()
  const aiCommentAllowed = desktopLicenseAllowsAiComment(license)
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
  const [aiSettings, setAiSettings] = useState<AiCommentSettings>(DEFAULT_AI_COMMENT_SETTINGS)
  const [savedAiSettings, setSavedAiSettings] = useState<AiCommentSettings>(DEFAULT_AI_COMMENT_SETTINGS)
  const [apiKeyStatus, setApiKeyStatus] = useState<AiCommentApiKeyStatus | null>(null)
  const [apiKeyDraft, setApiKeyDraft] = useState('')
  const [savingAiSettings, setSavingAiSettings] = useState(false)
  const [savingApiKey, setSavingApiKey] = useState(false)
  const [deletingApiKey, setDeletingApiKey] = useState(false)
  const [testingAi, setTestingAi] = useState(false)
  const [previewingAi, setPreviewingAi] = useState(false)
  const [testResult, setTestResult] = useState<AiCommentGenerationResult | null>(null)
  const [previewResult, setPreviewResult] = useState<AiCommentGenerationResult | null>(null)
  const [previewTitle, setPreviewTitle] = useState('A creator shares a simple desk setup tip')
  const [previewDescription, setPreviewDescription] = useState('')

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

  const aiDirty = useMemo(
    () => JSON.stringify(aiSettings) !== JSON.stringify(savedAiSettings),
    [aiSettings, savedAiSettings],
  )

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [nextSnapshot, nextAiSettings] = await Promise.all([
        loadCommentPools(currentPlatform),
        loadAiCommentSettings(),
      ])
      setSnapshot(nextSnapshot)
      setDrafts(snapshotToDrafts(nextSnapshot))
      setAiSettings(nextAiSettings)
      setSavedAiSettings(nextAiSettings)
      setApiKeyStatus(await getAiCommentApiKeyStatus(nextAiSettings.provider))
      setApiKeyDraft('')
      setTestResult(null)
      setPreviewResult(null)
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

  const updateAiSettings = <Key extends keyof AiCommentSettings>(key: Key, value: AiCommentSettings[Key]) => {
    if (key === 'enabled' && Boolean(value) && !aiCommentAllowed) {
      message.warning('当前套餐不支持 AI 评论')
      return
    }
    setAiSettings((current) => ({ ...current, [key]: value }))
    if (key === 'provider') {
      void refreshApiKeyStatus(String(value))
    }
    setTestResult(null)
    setPreviewResult(null)
  }

  const refreshApiKeyStatus = async (provider = aiSettings.provider) => {
    try {
      setApiKeyStatus(await getAiCommentApiKeyStatus(provider))
    } catch (error) {
      message.error(formatError(error))
    }
  }

  const saveAiSettingsOnly = async () => {
    setSavingAiSettings(true)
    try {
      const nextSettings = normalizeAiSettings(aiCommentAllowed ? aiSettings : { ...aiSettings, enabled: false })
      const result = await saveAiCommentSettings(nextSettings)
      setAiSettings(nextSettings)
      setSavedAiSettings(nextSettings)
      await refreshApiKeyStatus(nextSettings.provider)
      message.success(result.validation.valid ? 'AI 评论配置已保存' : 'AI 评论配置已保存，但配置校验存在提示')
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setSavingAiSettings(false)
    }
  }

  const saveApiKey = async () => {
    if (!apiKeyDraft.trim()) {
      message.warning('请输入 API Key')
      return
    }
    setSavingApiKey(true)
    try {
      const status = await saveAiCommentApiKey({
        provider: aiSettings.provider,
        apiKey: apiKeyDraft,
      })
      setApiKeyStatus(status)
      setApiKeyDraft('')
      message.success('API Key 已保存')
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setSavingApiKey(false)
    }
  }

  const deleteApiKey = () => {
    Modal.confirm({
      title: '删除 API Key',
      content: '删除后，AI 评论会在运行时回退评论池。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        setDeletingApiKey(true)
        try {
          setApiKeyStatus(await deleteAiCommentApiKey(aiSettings.provider))
          setApiKeyDraft('')
          message.success('API Key 已删除')
        } catch (error) {
          message.error(formatError(error))
        } finally {
          setDeletingApiKey(false)
        }
      },
    })
  }

  const testAiConnection = async () => {
    if (!aiCommentAllowed) {
      message.warning('当前套餐不支持 AI 评论')
      return
    }
    setTestingAi(true)
    try {
      const result = await testAiCommentConnection({ settings: normalizeAiSettings(aiSettings) })
      setTestResult(result)
      if (result.ok) {
        message.success('AI 评论连接正常')
      } else {
        message.warning(aiResultLabel(result.reason))
      }
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setTestingAi(false)
    }
  }

  const previewAi = async () => {
    if (!aiCommentAllowed) {
      message.warning('当前套餐不支持 AI 评论')
      return
    }
    if (!previewTitle.trim() && !previewDescription.trim()) {
      message.warning('请输入示例标题或描述')
      return
    }
    setPreviewingAi(true)
    try {
      const result = await previewAiComment({
        settings: normalizeAiSettings(aiSettings),
        title: previewTitle,
        description: previewDescription,
      })
      setPreviewResult(result)
      if (!result.ok) {
        message.warning(aiResultLabel(result.reason))
      }
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setPreviewingAi(false)
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

          <AiCommentSettingsPanel
            settings={aiCommentAllowed ? aiSettings : { ...aiSettings, enabled: false }}
            allowed={aiCommentAllowed}
            saved={apiKeyStatus?.saved ?? false}
            readable={apiKeyStatus?.readable ?? false}
            statusError={apiKeyStatus?.error}
            apiKeyDraft={apiKeyDraft}
            aiDirty={aiDirty}
            savingSettings={savingAiSettings}
            savingApiKey={savingApiKey}
            deletingApiKey={deletingApiKey}
            testing={testingAi}
            previewing={previewingAi}
            testResult={testResult}
            previewResult={previewResult}
            previewTitle={previewTitle}
            previewDescription={previewDescription}
            onUpdate={updateAiSettings}
            onApiKeyDraftChange={setApiKeyDraft}
            onSaveSettings={() => void saveAiSettingsOnly()}
            onSaveApiKey={() => void saveApiKey()}
            onDeleteApiKey={deleteApiKey}
            onTest={() => void testAiConnection()}
            onPreview={() => void previewAi()}
            onPreviewTitleChange={setPreviewTitle}
            onPreviewDescriptionChange={setPreviewDescription}
          />
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

function AiCommentSettingsPanel({
  settings,
  allowed,
  saved,
  readable,
  statusError,
  apiKeyDraft,
  aiDirty,
  savingSettings,
  savingApiKey,
  deletingApiKey,
  testing,
  previewing,
  testResult,
  previewResult,
  previewTitle,
  previewDescription,
  onUpdate,
  onApiKeyDraftChange,
  onSaveSettings,
  onSaveApiKey,
  onDeleteApiKey,
  onTest,
  onPreview,
  onPreviewTitleChange,
  onPreviewDescriptionChange,
}: {
  settings: AiCommentSettings
  allowed: boolean
  saved: boolean
  readable: boolean
  statusError?: string
  apiKeyDraft: string
  aiDirty: boolean
  savingSettings: boolean
  savingApiKey: boolean
  deletingApiKey: boolean
  testing: boolean
  previewing: boolean
  testResult: AiCommentGenerationResult | null
  previewResult: AiCommentGenerationResult | null
  previewTitle: string
  previewDescription: string
  onUpdate: <Key extends keyof AiCommentSettings>(key: Key, value: AiCommentSettings[Key]) => void
  onApiKeyDraftChange: (value: string) => void
  onSaveSettings: () => void
  onSaveApiKey: () => void
  onDeleteApiKey: () => void
  onTest: () => void
  onPreview: () => void
  onPreviewTitleChange: (value: string) => void
  onPreviewDescriptionChange: (value: string) => void
}) {
  return (
    <Card
      title="AI 评论"
      extra={
        <Button
          type="primary"
          icon={<Save size={16} />}
          loading={savingSettings}
          disabled={!aiDirty}
          onClick={onSaveSettings}
        >
          保存配置
        </Button>
      }
    >
      <Space direction="vertical" size={16} className="full-width">
        {!allowed ? (
          <Alert type="warning" showIcon message="当前套餐不支持 AI 评论，运行任务时会使用评论池。" />
        ) : null}
        {!saved ? (
          <Alert type="warning" showIcon message="未配置 API Key，开启后仍会回退评论池。" />
        ) : null}
        {saved && !readable ? (
          <Alert type="error" showIcon message="API Key 无法读取" description={statusError || '请重新保存 API Key。'} />
        ) : null}

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={8}>
            <Space direction="vertical" size={6} className="full-width">
              <Typography.Text strong>启用 AI 评论</Typography.Text>
              <Switch
                checked={settings.enabled}
                disabled={!allowed}
                onChange={(checked) => onUpdate('enabled', checked)}
              />
            </Space>
          </Col>
          <Col xs={24} lg={8}>
            <Space direction="vertical" size={6} className="full-width">
              <Typography.Text strong>Provider</Typography.Text>
              <Select
                value={settings.provider}
                options={[
                  { value: 'kimi_moonshot', label: 'Kimi Moonshot' },
                  { value: 'openai_compatible_custom', label: 'OpenAI Compatible' },
                ]}
                onChange={(value) => onUpdate('provider', value)}
              />
            </Space>
          </Col>
          <Col xs={24} lg={8}>
            <Space direction="vertical" size={6} className="full-width">
              <Typography.Text strong>语言</Typography.Text>
              <Select
                value={settings.language}
                options={[
                  { value: 'auto', label: '自动' },
                  { value: 'zh', label: '中文' },
                  { value: 'en', label: 'English' },
                ]}
                onChange={(value) => onUpdate('language', value)}
              />
            </Space>
          </Col>
          <Col xs={24} lg={12}>
            <Space direction="vertical" size={6} className="full-width">
              <Typography.Text strong>Base URL</Typography.Text>
              <Input value={settings.baseUrl} onChange={(event) => onUpdate('baseUrl', event.target.value)} />
            </Space>
          </Col>
          <Col xs={24} lg={12}>
            <Space direction="vertical" size={6} className="full-width">
              <Typography.Text strong>Model</Typography.Text>
              <Input value={settings.model} onChange={(event) => onUpdate('model', event.target.value)} />
            </Space>
          </Col>
          <Col xs={24} lg={12}>
            <Space direction="vertical" size={6} className="full-width">
              <Typography.Text strong>API Key</Typography.Text>
              <Input.Password
                value={apiKeyDraft}
                prefix={<KeyRound size={15} />}
                placeholder={saved ? '已保存；输入新值可覆盖' : '输入 API Key'}
                onChange={(event) => onApiKeyDraftChange(event.target.value)}
              />
              <Space wrap>
                <Tag color={saved && readable ? 'green' : 'gold'}>{saved && readable ? '已保存' : '未配置'}</Tag>
                <Button icon={<Save size={16} />} loading={savingApiKey} onClick={onSaveApiKey}>
                  保存 API Key
                </Button>
                <Button danger icon={<Trash2 size={16} />} loading={deletingApiKey} disabled={!saved} onClick={onDeleteApiKey}>
                  删除 API Key
                </Button>
              </Space>
            </Space>
          </Col>
          <Col xs={24} lg={12}>
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Space direction="vertical" size={6} className="full-width">
                  <Typography.Text strong>超时秒数</Typography.Text>
                  <InputNumber
                    min={1}
                    max={60}
                    value={settings.timeoutSeconds}
                    className="full-width"
                    onChange={(value) => onUpdate('timeoutSeconds', Number(value || 1))}
                  />
                </Space>
              </Col>
              <Col span={12}>
                <Space direction="vertical" size={6} className="full-width">
                  <Typography.Text strong>最大评论长度</Typography.Text>
                  <InputNumber
                    min={1}
                    max={300}
                    value={settings.maxCommentLength}
                    className="full-width"
                    onChange={(value) => onUpdate('maxCommentLength', Number(value || 1))}
                  />
                </Space>
              </Col>
            </Row>
            <Space direction="vertical" size={6} className="full-width" style={{ marginTop: 12 }}>
              <Typography.Text strong>敏感词黑名单</Typography.Text>
              <Input.TextArea
                rows={3}
                value={settings.blockedWords.join('\n')}
                placeholder="每行一个词"
                onChange={(event) => onUpdate('blockedWords', parseBlockedWords(event.target.value))}
              />
            </Space>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={10}>
            <Space direction="vertical" size={8} className="full-width">
              <Button icon={<PlugZap size={16} />} loading={testing} disabled={!allowed} onClick={onTest}>
                测试连接
              </Button>
              {testResult ? <AiCommentResultAlert result={testResult} compact /> : null}
            </Space>
          </Col>
          <Col xs={24} lg={14}>
            <Space direction="vertical" size={8} className="full-width">
              <Input
                value={previewTitle}
                placeholder="示例标题"
                onChange={(event) => onPreviewTitleChange(event.target.value)}
              />
              <Input.TextArea
                rows={2}
                value={previewDescription}
                placeholder="示例描述"
                onChange={(event) => onPreviewDescriptionChange(event.target.value)}
              />
              <Button icon={<Sparkles size={16} />} loading={previewing} disabled={!allowed} onClick={onPreview}>
                试生成
              </Button>
              {previewResult ? <AiCommentResultAlert result={previewResult} /> : null}
            </Space>
          </Col>
        </Row>
      </Space>
    </Card>
  )
}

function AiCommentResultAlert({
  result,
  compact = false,
}: {
  result: AiCommentGenerationResult
  compact?: boolean
}) {
  const type = result.ok ? 'success' : 'warning'
  const messageText = result.ok ? 'AI 评论连接正常' : aiResultLabel(result.reason)
  const description = result.ok
    ? result.comment || `${result.provider} / ${result.model} / ${result.latencyMs}ms`
    : result.error || `${result.provider} / ${result.model}`
  return <Alert type={type} showIcon message={messageText} description={compact ? undefined : description} />
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

function normalizeAiSettings(settings: AiCommentSettings): AiCommentSettings {
  return {
    ...settings,
    provider: settings.provider.trim() || DEFAULT_AI_COMMENT_SETTINGS.provider,
    baseUrl: settings.baseUrl.trim() || DEFAULT_AI_COMMENT_SETTINGS.baseUrl,
    model: settings.model.trim() || DEFAULT_AI_COMMENT_SETTINGS.model,
    timeoutSeconds: Math.max(1, Math.trunc(Number(settings.timeoutSeconds) || 1)),
    maxCommentLength: Math.max(1, Math.trunc(Number(settings.maxCommentLength) || 1)),
    language: settings.language.trim() || DEFAULT_AI_COMMENT_SETTINGS.language,
    blockedWords: settings.blockedWords.map((word) => word.trim()).filter(Boolean),
  }
}

function parseBlockedWords(text: string) {
  return text
    .split(/\r?\n/)
    .map((word) => word.trim())
    .filter(Boolean)
}

function aiResultLabel(reason: string) {
  const labels: Record<string, string> = {
    generated: '生成成功',
    missing_api_key: '未配置 API Key',
    missing_context: '缺少视频标题或描述',
    timeout: '请求超时',
    network_error: '网络请求失败',
    invalid_request: '请求参数错误',
    unauthorized: 'API Key 无效或未授权',
    forbidden: 'API Key 权限不足',
    not_found: '模型或接口不存在',
    rate_limited: '请求被限流',
    server_error: '模型服务端错误',
    http_error: '接口请求失败',
    invalid_response: '模型响应格式异常',
    unsupported_provider: 'Provider 不支持',
    credential_error: '密钥读取失败',
    runtime_error: '运行时错误',
    empty: '生成内容为空',
    multiline: '生成内容包含多行',
    url: '生成内容包含链接',
    mention: '生成内容包含 @',
    contact: '生成内容包含联系方式',
    too_long: '生成内容过长',
    blocked_word: '生成内容包含敏感词',
    prefixed_explanation: '生成内容包含解释前缀',
    unsafe_tone: '生成内容不是正向或中性评论',
    unsafe_context: '视频内容偏负面或争议，已跳过评论',
  }
  return labels[reason] || reason || '生成失败'
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
