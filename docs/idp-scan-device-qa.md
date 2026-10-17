# IDP Scan — device QA

Android emulator + one real device. Short screen capture per case.

1. Camera permission denied → choose-file path still works
2. Camera cancel → idle, no error spam
3. Rotate during capture → orientation corrected
4. Background mid-upload → close panel cancels Scan
5. Offline → soft fail on upload/run
6. Slow 3G → poll until Ready (10 min ceiling)

Web: `TAXIMATE_E2E_URL=… npx playwright test e2e/capture-scan.spec.ts`
