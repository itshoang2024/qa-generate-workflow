# Run Dashboard Design Alignment

Last updated: 2026-05-11

## Goal

Đưa `/runs/[id]` về đúng thiết kế trong `ui-design/qa-runs-dashboard`: dùng AppShell chung cho route, có ProviderStatusPills ở header, sidebar navigation cố định, font sans/mono đúng, và palette slate/indigo giống prototype.

## Chênh lệch thiết kế - thực tế

| Khu vực | Thiết kế gốc | Thực tế trước khi sửa | Cách sửa |
|---|---|---|---|
| Typography | Inter cho UI, JetBrains Mono cho ID/chip | `font-sans` rơi về Times New Roman do `--font-sans` tự tham chiếu | Đổi `layout.tsx` sang `Inter` + `JetBrains_Mono`, khai báo `--font-sans`/`--font-mono` trong `globals.css` |
| Palette | Dark slate: page `#020617`, card `#0f172a`, border `#1e293b`, accent indigo | Nền/card lệch về black/neutral shadcn default | Map lại CSS tokens light/dark theo design system |
| Header | Header 56px, provider pills, search command | Không có header chung | Thêm `AppShell` và `ProviderStatusPills` trong `src/components/app-shell.tsx` |
| Sidebar | Sidebar 256px với Workspace, Current run, Settings, user profile | Không có sidebar | Thêm sidebar dùng Next `<Link>` và active state theo pathname |
| Route shell | AppShell dùng một lần cho mọi route | `/runs/[id]` tự render content, layout không có shell | Bọc `{children}` bằng `<AppShell>` trong `src/app/layout.tsx` |
| Dashboard content | Content nằm trong main scroll area sau header/sidebar | Content chiếm toàn viewport, không có chrome | Giữ page dashboard hiện tại, nhưng đặt trong main area của AppShell |
| Type safety | Build sạch | `ArtifactTabs` dùng type `Coverage` không tồn tại; mutation callbacks sai chữ ký TanStack v5 | Đổi sang `CoverageReport` và truyền đủ callback args |

## Tasks

- [x] Đọc design handoff: `README.md`, chat transcript, `Run Dashboard.html`, `tokens.css`, `Chrome.jsx`, `RunDashboard.jsx`.
  Verify: xác định được sidebar/header/token/font trực tiếp từ prototype.

- [x] Sửa typography tokens.
  Verify: browser computed `bodyFont` và `h1Font` là `Inter, "Inter Fallback"`.

- [x] Sửa palette global theo slate/indigo design system.
  Verify: browser computed `bodyBg = rgb(2, 6, 23)` và `cardBg = rgb(15, 23, 42)`.

- [x] Thêm `<AppShell>` dùng chung ở layout.
  Verify: `/runs/run_87a8f69786fc` render `aside` rộng `256px` và `header` cao `56px`.

- [x] Thêm `<ProviderStatusPills>` đọc `useProvidersStatus()`.
  Verify: header hiển thị live state từ backend, ví dụ `AI openai`, `Notion real`, `repo supabase`.

- [x] Thêm sidebar navigation theo thiết kế.
  Verify: Current run links trỏ về dashboard, HIL queue, sync log, risk, sign off và active state dựa trên `usePathname()`.

- [x] Sửa lỗi typecheck phát sinh trong dashboard/mutations.
  Verify: `npx tsc --noEmit` pass.

- [x] Chạy verification cuối.
  Verify: `npm run lint`, `npx tsc --noEmit`, `npm run build` đều pass; screenshot kiểm tra lưu tại `.next/dashboard-appshell-check.png`.

- [x] Fix invalid loading markup that caused Next.js hydration warnings.
  Verify: route header loading uses inline `<span>` skeletons, the subtitle wrapper is a `<div>`, and browser console no longer reports `<div>` inside `<p>`.

- [x] Sync global tracking docs after implementation.
  Verify: `frontend/PLAN.md` and `frontend/TASKS.md` reflect shipped data layer, AppShell, provider pills, sidebar navigation, run dashboard, and remaining open work.

## Notes

- Provider pill text dùng dữ liệu thật từ `/providers/status`, nên có thể khác mock text trong ảnh thiết kế nếu backend đang chạy với provider khác.
- AppShell hiện áp dụng cho mọi route hiện có. Các target route như `/projects`, `/runs/[id]/risk`, `/runs/[id]/sync-log` vẫn là các màn hình tương lai nếu chưa được implement.
