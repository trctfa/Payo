# 輸入法通知快捷鈕

紅米 / HyperOS 用的小工具：啟用後在通知列留下常駐通知，點通知或「切換」就會跳出系統輸入法選單（可選注音、無蝦米等）。

## 功能

- 常駐通知快捷鈕
- 點通知 → 開啟輸入法選單
- 通知上的「切換」按鈕同效果
- 重開機後可自動恢復（需允許自啟動）
- 「測試」按鈕可先確認選單是否正常

## 沒有電腦？只用手機安裝（推薦）

直接看：[`只用手機安裝.md`](只用手機安裝.md)

安裝檔：[`release/ime-switcher.apk`](release/ime-switcher.apk)

## 用 Android Studio 安裝到手機

**有電腦、不會寫程式？看這裡：**  
[`一步一步安裝教學.md`](一步一步安裝教學.md)

精簡版：

1. 安裝 [Android Studio](https://developer.android.com/studio)
2. 開啟本資料夾 `ime-switcher`
3. 用 USB 連接紅米 12 5G Pro，開啟「開發人員選項」與「USB 偵錯」
4. 在 Android Studio 按 Run（綠色三角形）安裝到手機
5. 開啟 App → 允許通知 → 按「啟用通知快捷鈕」

## 紅米 / HyperOS 必做設定

否則通知可能被系統清掉：

1. **設定 → 應用程式 → 輸入法快捷鈕 → 省電策略 → 無限制**
2. **允許自啟動**
3. **允許顯示通知**
4. 若通知被收進靜音區塊：通知管理 →「輸入法快捷」頻道 → 改為顯示

## 使用方式

1. 啟用後，下拉通知列會看到「切換輸入法」
2. 點通知本體或「切換」
3. 在跳出的選單選注音或其他輸入法

## 技術說明

Android 不允許一般 App 直接強制切換到指定輸入法，因此本 App 呼叫系統的 `InputMethodManager.showInputMethodPicker()`，用透明 Activity 從通知可靠地叫出選單（比在 BroadcastReceiver 裡直接呼叫更穩，尤其在 MIUI / HyperOS）。

套件名稱：`com.payo.imeswitcher`
