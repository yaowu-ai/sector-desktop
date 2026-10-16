import type { PublishMode, PublishRequest } from './types';
export const PUBLISH_STATUS_LABELS = {
  queued: '等待执行', running: '正在发布', intervention_required: '需要人工处理',
  committing: '正在提交', verifying: '正在核验', verified: '已确认成功',
  pending_confirmation: '待确认', failed: '发布失败', skipped: '已跳过', cancelled: '已取消',
} as const;
export const PUBLISH_PHASE_LABELS: Record<string, string> = {
  queued: '等待执行', opening: '打开浏览器', authenticating: '检查登录', baseline: '记录主页基线', uploading: '上传视频',
  uploaded: '上传完成', prompts: '处理提示', caption: '填写文案', submitting: '提交发布', verifying: '主页核验', finished: '执行结束',
};
export function formatPublishEvidence(raw?: string | null): string {
  if (!raw) return '暂无核验证据；未保存截图';
  try {
    const evidence: unknown = JSON.parse(raw);
    if (!evidence || typeof evidence !== 'object' || Array.isArray(evidence)) return '核验证据无法读取';
    const fields = evidence as Record<string, unknown>;
    const value = (key: string) => typeof fields[key] === 'string' ? fields[key] as string : '';
    const observedAt = value('observed_at');
    const date = observedAt ? new Date(observedAt) : undefined;
    const basis: Record<string, string> = { exact_post_id_and_detail: '作品 ID、作者及文案一致', unconfirmed: '尚未确认本次作品' };
    return [
      `核验时间：${date && !Number.isNaN(date.getTime()) ? date.toLocaleString('zh-CN', { hour12: false }) : '未记录'}`,
      `确认依据：${basis[value('match_basis')] ?? '未记录'}`,
      `核验说明：${value('reason') || '未记录'}`,
      `作品 ID：${value('correlated_post_id') || '未获取'}`,
      `候选作品数：${Array.isArray(fields.candidate_ids) ? fields.candidate_ids.length : 0}`,
      value('screenshot_path') ? `截图路径：${value('screenshot_path')}` : '未保存截图',
    ].join('\n');
  } catch { return '核验证据无法读取'; }
}
export function buildPublishRequest(requestId: string, mode: PublishMode, accountIds: string[], videoPath: string, caption: string): PublishRequest {
  if (!videoPath) throw new Error('请选择本地视频');
  if (caption.length > 4000) throw new Error('文案最多 4000 个字符');
  if (caption.includes('\0')) throw new Error('文案不能包含无效控制字符');
  const ids = [...new Set(accountIds)];
  if (mode === 'single' && ids.length !== 1) throw new Error('请选择一个账号');
  if (mode === 'selected' && !ids.length) throw new Error('请选择执行账号');
  return { requestId, platform: 'tiktok', mode, accountIds: mode === 'all' ? [] : ids, videoPath, caption };
}
export function safeTikTokPostUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && ['www.tiktok.com', 'tiktok.com'].includes(url.hostname) && !url.port && !url.username && !url.password && /^\/@[^/]+\/video\/\d+\/?$/.test(url.pathname) && !url.search && !url.hash;
  } catch { return false; }
}
export function publicationDateFilter(from: string, to: string): { from?: string; to?: string } {
  const localDate = (value: string) => { const [y, m, d] = value.split('-').map(Number); return new Date(y, m - 1, d); };
  const start = from ? localDate(from) : undefined;
  const end = to ? localDate(to) : undefined;
  if (start && end && start > end) throw new Error('开始日期不能晚于结束日期');
  if (end) end.setDate(end.getDate() + 1);
  return { from: start?.toISOString(), to: end?.toISOString() };
}
