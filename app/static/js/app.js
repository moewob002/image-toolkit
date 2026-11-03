document.addEventListener('DOMContentLoaded', () => {
  // --- Theme Management (Light / Dark Mode) ---
  const themeToggleBtn = document.getElementById('theme-toggle-btn');
  
  function getPreferredTheme() {
    const saved = localStorage.getItem('image-toolkit-theme');
    if (saved) return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('image-toolkit-theme', theme);
  }

  // Hydrate initial theme
  applyTheme(getPreferredTheme());

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      showToast(`Switched to ${next === 'dark' ? 'Dark' : 'Light'} theme`, 'info');
    });
  }

  // Listen for OS theme changes if user hasn't explicitly set a preference
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('image-toolkit-theme')) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });

  // --- Application State ---
  let currentTab = 'converter';
  let queuedFiles = [];
  let processedResults = [];
  let isProcessing = false;

  // --- DOM Elements ---
  const tabBtns = document.querySelectorAll('.tab-btn');
  const toolForms = document.querySelectorAll('.tool-settings-form');
  const settingsTitle = document.getElementById('settings-title');
  const settingsSubtitle = document.getElementById('settings-subtitle');
  
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const queueContainer = document.getElementById('queue-container');
  const queueItems = document.getElementById('queue-items');
  const queueCount = document.getElementById('queue-count');
  const queueTotalSize = document.getElementById('queue-total-size');
  const clearQueueBtn = document.getElementById('clear-queue-btn');

  const processBtn = document.getElementById('process-btn');
  const processBtnText = document.getElementById('process-btn-text');
  const progressContainer = document.getElementById('progress-container');
  const progressFill = document.getElementById('progress-fill');
  const progressStatus = document.getElementById('progress-status');
  const progressPercent = document.getElementById('progress-percent');

  const resultsSection = document.getElementById('results-section');
  const resultsGrid = document.getElementById('results-grid');
  const resultsSummary = document.getElementById('results-summary');
  const downloadZipBtn = document.getElementById('download-zip-btn');
  const newBatchBtn = document.getElementById('new-batch-btn');
  const toastContainer = document.getElementById('toast-container');

  // Modal Elements
  const previewModal = document.getElementById('preview-modal');
  const modalImg = document.getElementById('modal-img');
  const modalTitle = document.getElementById('modal-title');
  const modalMeta = document.getElementById('modal-meta');
  const modalDownloadLink = document.getElementById('modal-download-link');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const modalPreviewWrapper = document.getElementById('modal-preview-wrapper');

  // --- Tab Descriptions ---
  const tabDescriptions = {
    converter: {
      title: 'Image Converter Settings',
      subtitle: 'Convert between 8 web and archival formats with quality and dimension control'
    },
    compressor: {
      title: 'Image Compressor Settings',
      subtitle: 'Reduce file size with smart presets, custom quality sliders, and optional scaling'
    },
    bgremover: {
      title: 'AI Background Remover Settings',
      subtitle: 'Salience segmentation powered by local ONNX u2net with custom backdrop replacement'
    }
  };

  // --- Tab Switching Navigation ---
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      currentTab = btn.dataset.tab;

      toolForms.forEach(f => f.classList.remove('active'));
      const activeForm = document.getElementById(`${currentTab}-form`);
      if (activeForm) activeForm.classList.add('active');

      // Update settings card headers
      if (tabDescriptions[currentTab]) {
        if (settingsTitle) settingsTitle.textContent = tabDescriptions[currentTab].title;
        if (settingsSubtitle) settingsSubtitle.textContent = tabDescriptions[currentTab].subtitle;
      }

      updateProcessBtnText();
    });
  });

  function updateProcessBtnText() {
    const count = queuedFiles.length;
    const countLabel = count === 1 ? '1 Image' : `${count} Images`;
    if (currentTab === 'converter') {
      processBtnText.textContent = count > 0 ? `Convert ${countLabel}` : 'Convert Images';
    } else if (currentTab === 'compressor') {
      processBtnText.textContent = count > 0 ? `Compress ${countLabel}` : 'Compress Images';
    } else if (currentTab === 'bgremover') {
      processBtnText.textContent = count > 0 ? `Remove Background (${countLabel})` : 'Remove Background';
    }
  }

  // --- Drag and Drop Handlers ---
  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const files = Array.from(e.dataTransfer.files);
    handleFilesSelected(files);
  });

  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', () => {
    handleFilesSelected(Array.from(fileInput.files));
    fileInput.value = '';
  });

  // --- File Selection & Validation ---
  const SUPPORTED_EXTS = ['jpg', 'jpeg', 'png', 'webp', 'avif', 'gif', 'bmp', 'tiff', 'tif', 'ico'];

  function handleFilesSelected(newFiles) {
    if (!newFiles || newFiles.length === 0) return;

    let validCount = 0;
    for (const file of newFiles) {
      const ext = file.name.split('.').pop().toLowerCase();
      if (!SUPPORTED_EXTS.includes(ext) && !file.type.startsWith('image/')) {
        showToast(`Skipped "${file.name}": Unsupported image format`, 'error');
        continue;
      }
      
      // Check duplicate
      const isDuplicate = queuedFiles.some(f => f.name === file.name && f.size === file.size);
      if (!isDuplicate) {
        queuedFiles.push(file);
        validCount++;
      }
    }

    if (validCount > 0) {
      showToast(`Added ${validCount} file${validCount > 1 ? 's' : ''} to processing queue`, 'success');
    }

    renderQueue();
  }

  // --- Render File Queue ---
  function renderQueue() {
    queueItems.innerHTML = '';
    const totalFiles = queuedFiles.length;

    if (totalFiles === 0) {
      queueContainer.style.display = 'none';
      queueCount.textContent = '0 queued';
      if (queueTotalSize) queueTotalSize.textContent = '';
      processBtn.disabled = true;
      updateProcessBtnText();
      return;
    }

    queueContainer.style.display = 'flex';
    queueCount.textContent = `${totalFiles} queued`;
    
    // Total size calculation
    const totalBytes = queuedFiles.reduce((acc, f) => acc + f.size, 0);
    if (queueTotalSize) {
      queueTotalSize.textContent = `• ${formatBytes(totalBytes)} total`;
    }

    processBtn.disabled = false;
    updateProcessBtnText();

    queuedFiles.forEach((file, index) => {
      const item = document.createElement('div');
      item.className = 'queue-item';

      const thumb = document.createElement('img');
      thumb.className = 'queue-thumb';
      thumb.alt = file.name;
      const objectUrl = URL.createObjectURL(file);
      thumb.src = objectUrl;
      thumb.onload = () => URL.revokeObjectURL(objectUrl);

      const info = document.createElement('div');
      info.className = 'queue-info';

      const name = document.createElement('div');
      name.className = 'queue-name';
      name.textContent = file.name;
      name.title = file.name;

      const meta = document.createElement('div');
      meta.className = 'queue-meta';
      const ext = file.name.split('.').pop().toUpperCase();
      meta.textContent = `${ext} • ${formatBytes(file.size)}`;

      info.appendChild(name);
      info.appendChild(meta);

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'queue-remove-btn';
      removeBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      `;
      removeBtn.title = 'Remove from queue';
      removeBtn.setAttribute('aria-label', `Remove ${file.name}`);
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        queuedFiles.splice(index, 1);
        renderQueue();
      });

      item.appendChild(thumb);
      item.appendChild(info);
      item.appendChild(removeBtn);
      queueItems.appendChild(item);
    });
  }

  clearQueueBtn.addEventListener('click', () => {
    queuedFiles = [];
    renderQueue();
    showToast('Queue cleared', 'info');
  });

  // --- Tool Settings Event Listeners ---
  // 1. Converter Settings
  const convQuality = document.getElementById('conv-quality');
  const convQualityVal = document.getElementById('conv-quality-val');
  if (convQuality && convQualityVal) {
    convQuality.addEventListener('input', () => {
      convQualityVal.textContent = `${convQuality.value}%`;
    });
  }

  const convFormat = document.getElementById('conv-format');
  const convMatteGroup = document.getElementById('conv-matte-group');
  if (convFormat && convMatteGroup) {
    convFormat.addEventListener('change', () => {
      const nonTransparent = ['JPEG', 'BMP'].includes(convFormat.value);
      convMatteGroup.style.display = nonTransparent ? 'flex' : 'none';
    });
  }

  const convMatte = document.getElementById('conv-matte');
  const convMatteHex = document.getElementById('conv-matte-hex');
  if (convMatte && convMatteHex) {
    convMatte.addEventListener('input', () => {
      convMatteHex.textContent = convMatte.value.toUpperCase();
    });
  }

  // 2. Compressor Settings
  const presetRadios = document.querySelectorAll('input[name="preset"]');
  const customQualityGroup = document.getElementById('comp-custom-quality-group');
  const compQuality = document.getElementById('comp-quality');
  const compQualityVal = document.getElementById('comp-quality-val');
  
  presetRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      document.querySelectorAll('.preset-card').forEach(c => c.classList.remove('checked'));
      radio.closest('.preset-card').classList.add('checked');
      if (customQualityGroup) {
        customQualityGroup.style.display = radio.value === 'custom' ? 'flex' : 'none';
      }
    });
  });

  if (compQuality && compQualityVal) {
    compQuality.addEventListener('input', () => {
      compQualityVal.textContent = `${compQuality.value}%`;
    });
  }

  const resizeModeSelect = document.getElementById('comp-resize-mode');
  const compPercentGroup = document.getElementById('comp-percentage-group');
  const compPercent = document.getElementById('comp-percent');
  const compPercentVal = document.getElementById('comp-percent-val');
  const compDimsGroup = document.getElementById('comp-dimensions-group');

  if (resizeModeSelect) {
    resizeModeSelect.addEventListener('change', () => {
      if (compPercentGroup) compPercentGroup.style.display = resizeModeSelect.value === 'percentage' ? 'flex' : 'none';
      if (compDimsGroup) compDimsGroup.style.display = resizeModeSelect.value === 'dimensions' ? 'flex' : 'none';
    });
  }

  if (compPercent && compPercentVal) {
    compPercent.addEventListener('input', () => {
      compPercentVal.textContent = `${compPercent.value}%`;
    });
  }

  // 3. Background Remover Settings
  const bgTypeRadios = document.querySelectorAll('input[name="bg_type"]');
  const bgColorPickerGroup = document.getElementById('bg-color-picker-group');
  const bgImageUploadGroup = document.getElementById('bg-image-upload-group');
  const bgColorPicker = document.getElementById('bg-color-picker');
  const bgColorPreview = document.getElementById('bg-color-preview');
  const bgColorHex = document.getElementById('bg-color-hex');

  bgTypeRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      document.querySelectorAll('.bg-choice-card').forEach(c => c.classList.remove('checked'));
      radio.closest('.bg-choice-card').classList.add('checked');
      if (bgColorPickerGroup) bgColorPickerGroup.style.display = radio.value === 'color' ? 'flex' : 'none';
      if (bgImageUploadGroup) bgImageUploadGroup.style.display = radio.value === 'image' ? 'flex' : 'none';
    });
  });

  if (bgColorPicker) {
    bgColorPicker.addEventListener('input', () => {
      const color = bgColorPicker.value.toUpperCase();
      if (bgColorPreview) bgColorPreview.style.backgroundColor = color;
      if (bgColorHex) bgColorHex.textContent = color;
    });
  }

  // --- Prevent Accidental Reloads during Queue or Processing ---
  window.addEventListener('beforeunload', (e) => {
    if (isProcessing || queuedFiles.length > 0) {
      e.preventDefault();
      e.returnValue = '';
      return '';
    }
  });

  // --- Process Action Handler ---
  processBtn.addEventListener('click', async () => {
    if (queuedFiles.length === 0 || isProcessing) return;

    isProcessing = true;
    processBtn.disabled = true;
    progressContainer.style.display = 'flex';
    progressFill.style.width = '10%';
    progressPercent.textContent = '10%';
    progressStatus.textContent = 'Preparing files...';

    try {
      const formData = new FormData();
      queuedFiles.forEach(f => formData.append('files', f));

      let endpoint = '';
      if (currentTab === 'converter') {
        endpoint = '/api/convert';
        formData.append('target_format', document.getElementById('conv-format').value);
        formData.append('quality', document.getElementById('conv-quality').value);
        
        const w = document.getElementById('conv-width').value;
        const h = document.getElementById('conv-height').value;
        if (w) formData.append('width', w);
        if (h) formData.append('height', h);
        formData.append('preserve_aspect_ratio', document.getElementById('conv-aspect').checked);
        formData.append('background_color', document.getElementById('conv-matte').value);
      } else if (currentTab === 'compressor') {
        endpoint = '/api/compress';
        const presetInput = document.querySelector('input[name="preset"]:checked');
        const preset = presetInput ? presetInput.value : 'balanced';
        formData.append('preset', preset);
        if (preset === 'custom' && compQuality) {
          formData.append('quality', compQuality.value);
        }
        const targetFmt = document.getElementById('comp-format').value;
        if (targetFmt) formData.append('target_format', targetFmt);

        const rMode = resizeModeSelect ? resizeModeSelect.value : 'none';
        if (rMode !== 'none') {
          formData.append('resize_mode', rMode);
          if (rMode === 'percentage' && compPercent) {
            formData.append('resize_percentage', compPercent.value);
          } else if (rMode === 'dimensions') {
            const cw = document.getElementById('comp-width').value;
            const ch = document.getElementById('comp-height').value;
            if (cw) formData.append('width', cw);
            if (ch) formData.append('height', ch);
          }
        }
      } else if (currentTab === 'bgremover') {
        endpoint = '/api/remove-bg';
        const bgTypeInput = document.querySelector('input[name="bg_type"]:checked');
        const bgType = bgTypeInput ? bgTypeInput.value : 'transparent';
        formData.append('bg_type', bgType);
        if (bgType === 'color' && bgColorPicker) {
          formData.append('bg_color', bgColorPicker.value);
        } else if (bgType === 'image') {
          const customBgInput = document.getElementById('bg-custom-image-input');
          if (customBgInput && customBgInput.files[0]) {
            formData.append('bg_image', customBgInput.files[0]);
          }
        }
      }

      // Execute upload with real progress tracking via XMLHttpRequest
      const data = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', endpoint);

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            // Map upload to 10% - 65%
            const uploadPct = Math.round(10 + (e.loaded / e.total) * 55);
            progressFill.style.width = `${uploadPct}%`;
            progressPercent.textContent = `${uploadPct}%`;
            progressStatus.textContent = `Uploading images (${Math.round((e.loaded / e.total) * 100)}%)...`;
          }
        };

        xhr.upload.onload = () => {
          progressFill.style.width = '75%';
          progressPercent.textContent = '75%';
          progressStatus.textContent = 'Processing on-device offline...';
        };

        xhr.onload = () => {
          try {
            const response = JSON.parse(xhr.responseText);
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(response);
            } else {
              reject(new Error(response.detail || response.error || `Server error ${xhr.status}`));
            }
          } catch (err) {
            reject(new Error(`Invalid server response format (${xhr.status})`));
          }
        };

        xhr.onerror = () => reject(new Error('Network error or server unreachable'));
        xhr.ontimeout = () => reject(new Error('Request timed out'));

        xhr.send(formData);
      });

      progressFill.style.width = '100%';
      progressPercent.textContent = '100%';
      progressStatus.textContent = 'Completed!';

      setTimeout(() => {
        progressContainer.style.display = 'none';
      }, 700);

      displayResults(data.results || []);
      showToast(`Processed ${data.successful} of ${data.total} images successfully!`, 'success');
    } catch (err) {
      progressContainer.style.display = 'none';
      showToast(err.message || 'Processing failed', 'error');
    } finally {
      isProcessing = false;
      processBtn.disabled = false;
    }
  });

  // --- Results Display & Lightbox Modal ---
  function displayResults(results) {
    processedResults = results.filter(r => r.status === 'success');
    resultsGrid.innerHTML = '';

    if (results.length === 0) {
      resultsSection.style.display = 'none';
      return;
    }

    resultsSection.style.display = 'flex';
    resultsSummary.textContent = `${processedResults.length} of ${results.length} files processed without errors.`;

    results.forEach(res => {
      const card = document.createElement('div');
      card.className = 'result-card';

      if (res.status === 'error') {
        card.innerHTML = `
          <div class="result-body">
            <div class="result-meta-row">
              <span class="result-name text-danger">${res.original_filename}</span>
              <span class="badge-format text-danger">ERROR</span>
            </div>
            <p class="result-submeta text-danger">${res.error || 'Failed to process file'}</p>
          </div>
        `;
      } else {
        const isTransparent = ['PNG', 'WEBP', 'AVIF'].includes(res.target_format || res.format);
        const savingsBadge = res.savings_percent !== undefined
          ? `<span class="stats-badge-pill">-${res.savings_percent}% (${formatBytes(res.original_size_bytes)} → ${formatBytes(res.compressed_size_bytes)})</span>`
          : '';

        card.innerHTML = `
          <div class="result-preview-container ${isTransparent ? 'checker-bg' : ''}" title="Click to inspect in fullscreen">
            <img class="result-img" src="${res.preview_url}" alt="${res.original_filename}" loading="lazy">
            <div class="result-preview-overlay">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
              <span>Inspect</span>
            </div>
          </div>
          <div class="result-body">
            <div class="result-meta-row">
              <span class="result-name" title="${res.original_filename}">${res.original_filename}</span>
              <span class="badge-format">${res.target_format || res.format}</span>
            </div>
            <div class="result-meta-row result-submeta">
              <span>${res.width} × ${res.height} px</span>
              <span>${formatBytes(res.size_bytes || res.compressed_size_bytes)}</span>
            </div>
            ${savingsBadge}
            <div class="result-actions-row">
              <a href="${res.download_url}" download class="btn-card-download">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                <span>Download</span>
              </a>
              <button type="button" class="btn-card-preview" title="Inspect in modal">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </div>
        `;

        // Lightbox Inspect triggers
        const previewBox = card.querySelector('.result-preview-container');
        const previewBtn = card.querySelector('.btn-card-preview');
        const openModalHandler = () => openPreviewModal(res);
        previewBox.addEventListener('click', openModalHandler);
        previewBtn.addEventListener('click', openModalHandler);
      }

      resultsGrid.appendChild(card);
    });

    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // --- Lightbox Modal Logic ---
  function openPreviewModal(res) {
    if (!previewModal) return;
    modalImg.src = res.preview_url;
    modalTitle.textContent = res.original_filename;
    const formatName = res.target_format || res.format;
    const sizeStr = formatBytes(res.size_bytes || res.compressed_size_bytes);
    modalMeta.textContent = `${formatName} • ${res.width} × ${res.height} px • ${sizeStr}`;
    modalDownloadLink.href = res.download_url;
    modalDownloadLink.download = res.converted_filename || res.compressed_filename || res.processed_filename || 'image';

    const isTransparent = ['PNG', 'WEBP', 'AVIF'].includes(formatName);
    if (modalPreviewWrapper) {
      modalPreviewWrapper.className = `modal-body-preview ${isTransparent ? 'checker-bg' : ''}`;
    }

    previewModal.style.display = 'flex';
  }

  function closePreviewModal() {
    if (previewModal) previewModal.style.display = 'none';
  }

  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closePreviewModal);
  if (previewModal) {
    previewModal.addEventListener('click', (e) => {
      if (e.target === previewModal) closePreviewModal();
    });
  }
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && previewModal && previewModal.style.display !== 'none') {
      closePreviewModal();
    }
  });

  // --- Download All as ZIP ---
  downloadZipBtn.addEventListener('click', async () => {
    const filenames = processedResults.map(r => r.converted_filename || r.compressed_filename || r.processed_filename).filter(Boolean);
    if (filenames.length === 0) {
      showToast('No processed files available to zip', 'error');
      return;
    }

    try {
      downloadZipBtn.disabled = true;
      downloadZipBtn.innerHTML = `
        <span class="progress-spinner" style="border-top-color: #fff; width: 14px; height: 14px;"></span>
        <span>Zipping...</span>
      `;
      
      const response = await fetch('/api/download-zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filenames: filenames,
          zip_name: `toolkit_export_${Date.now()}.zip`,
        }),
      });

      if (!response.ok) throw new Error('Failed to generate ZIP archive');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `toolkit_export_${Date.now()}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast('ZIP archive downloaded successfully', 'success');
    } catch (err) {
      showToast(err.message || 'ZIP creation failed', 'error');
    } finally {
      downloadZipBtn.disabled = false;
      downloadZipBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        <span>Download All as ZIP</span>
      `;
    }
  });

  // --- New Batch Reset Button ---
  newBatchBtn.addEventListener('click', () => {
    queuedFiles = [];
    processedResults = [];
    renderQueue();
    resultsSection.style.display = 'none';
    window.scrollTo({ top: 0, behavior: 'smooth' });
    showToast('Ready for new batch', 'info');
  });

  // --- Utility Functions ---
  function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = '';
    if (type === 'success') {
      icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'error') {
      icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else {
      icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `
      ${icon}
      <span>${message}</span>
    `;
    
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(16px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
});
