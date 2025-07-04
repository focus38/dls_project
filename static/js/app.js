MAX_FILE_SIZE_MB = 3
MAX_FILE_SIZE_KB = 1024 * MAX_FILE_SIZE_MB

$(document).ready(function() {
    // Элементы интерфейса
    const $uploadBtn = $('#uploadBtn');
    const $uploadSpinner = $('#uploadSpinner');
    const $imageUpload = $('#imageUpload');
    const $uploadStatus = $('#uploadStatus');
    const $fileUuid = $('#fileUuid');
    const $statusBadge = $('#statusBadge');
    const $previewLeftContainer = $('#previewLeftContainer');
    const $previewRightContainer = $('#previewRightContainer');
    const $fileInfo = $('#fileInfo');
    const $imagePreview = $('#imagePreview');
    const $processedImage = $('#processedImage');
    const $indicatorValues = $('#indicatorValues');

    let currentUuid = null;
    let checkStatusInterval = null;

    // Обработчик изменения файла. Показываем файл в preview области.
    $imageUpload.on('change', function() {
        if (this.files.length) {
            const file = this.files[0];
            const reader = new FileReader();
            const fileSize = file.size / 1024; // KB
            // Показываем информацию о файле
            $fileInfo.empty()
            $fileInfo.append(`<li class="list-group-item list-group-item-dark bgc-light">Имя: ${file.name}, Размер: ${(file.size / 1024).toFixed(2)} KB, Тип: ${file.type}</li>`);
            
            $previewRightContainer.hide();
            $previewLeftContainer.hide();
            $indicatorValues.empty();
            
            if (!file.type.match('image.*')) {
                alert('Пожалуйста, выберите файл изображения.');
                return;
            }
            if (fileSize > MAX_FILE_SIZE_KB) {
                alert('Пожалуйста, выберите файл размером меньше ' + MAX_FILE_SIZE_MB + 'MB.');
                return;
            }
            // Для изображений - создаем превью
            reader.onload = function(e) {
                $imagePreview.attr('src', e.target.result);
                $previewRightContainer.hide();
                $uploadStatus.find('.alert').hide();
                $previewLeftContainer.show();
                $indicatorValues.empty();
            }
            reader.readAsDataURL(file);
        }
    });

    // Обработчик загрузки файла
    $uploadBtn.on('click', async function() {
        if ($imageUpload[0].files.length === 0) {
            alert('Пожалуйста, выберите файл');
            return;
        }

        const file = $imageUpload[0].files[0];
        
        try {
            // Показываем spinner
            $uploadSpinner.removeClass("d-none");
            $uploadBtn.addClass("disabled");
            
            // Отправка файла на сервер
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await $.ajax({
                url: '/upload/',
                type: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                xhr: function() {
                    const xhr = new window.XMLHttpRequest();
                    xhr.upload.addEventListener('loadend', function(e) {
                        $uploadSpinner.addClass("d-none");
                        $uploadBtn.removeClass("disabled");
                    });
                    return xhr;
                }
            });
            
            currentUuid = response.uuid;
            
            // Обновляем UI
            $fileUuid.text(currentUuid);
            $statusBadge.text('В очереди').removeClass().addClass('badge bg-secondary status-badge ms-2');
            $uploadStatus.find('.alert').show();
            
            // Запускаем проверку статуса
            startStatusChecking();
            
        } catch (error) {
            console.error('Error:', error);
            alert('Ошибка при загрузке файла: ' + error.responseJSON?.detail || error.statusText);
        } finally {
            $uploadSpinner.addClass("d-none");
            $uploadBtn.removeClass("disabled");
        }
    });

    // Функция проверки статуса обработки
    function startStatusChecking() {
        if (checkStatusInterval) {
            clearInterval(checkStatusInterval);
        }
        
        checkStatusInterval = setInterval(async () => {
            try {
                const statusData = await $.get(`/status/${currentUuid}`);
                
                if (statusData.status === 'processed') {
                    // Обработка завершена
                    $statusBadge.text('Готово').removeClass().addClass('badge bg-success status-badge ms-2');
                    clearInterval(checkStatusInterval);
                    
                    // Загружаем результат
                    await loadProcessedImage();
                } else if (statusData.status === 'processing') {
                    $statusBadge.text('Обрабатывается').removeClass().addClass('badge bg-warning text-dark status-badge ms-2');
                }
                
            } catch (error) {
                console.error('Status check error:', error);
                clearInterval(checkStatusInterval);
                $statusBadge.text('Ошибка').removeClass().addClass('badge bg-danger status-badge ms-2');
            }
        }, 2000); // Проверяем каждые 2000 млс.
    }

    // Загрузка обработанного изображения
    async function loadProcessedImage() {
        try {
            // Создаем временный URL для изображения
            const imageUrl = `/result/${currentUuid}`;
            
            $processedImage.attr('src', imageUrl)
                .on('load', function() {
                    $previewRightContainer.show();
                })
                .on('error', function() {
                    throw new Error('Не удалось загрузить изображение');
                });
            const indicatorValues = await $.get(`/values/${currentUuid}`);
            $indicatorValues.empty();
            if (indicatorValues != null && indicatorValues.values != null) {
                for(let i in indicatorValues.values) {
                    $indicatorValues.append('<li class="list-group-item list-group-item-light">Показание: ' + indicatorValues.values[i] + "</li>")
                }
            }
        } catch (error) {
            console.error('Error loading result:', error);
            $statusBadge.text('Ошибка').removeClass().addClass('badge bg-danger status-badge ms-2');
        }
    }
});
