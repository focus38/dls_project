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

    let currentUuid = null;
    let checkStatusInterval = null;

    // Обработчик изменения файла. Показываем файл в preview области.
    $imageUpload.on('change', function() {
        if (this.files.length) {
            const file = this.files[0];
            const reader = new FileReader();
            
            // Показываем информацию о файле
            $fileInfo.html(`Имя: ${file.name},  Размер: ${(file.size / 1024).toFixed(2)} KB, Тип: ${file.type}`);
            // Для изображений - создаем превью
            if (file.type.match('image.*')) {
                reader.onload = function(e) {
                    $imagePreview.attr('src', e.target.result);
                    $previewRightContainer.hide();
                    $uploadStatus.find('.alert').hide();
                    $previewLeftContainer.show();
                }
                reader.readAsDataURL(file);
            } else {
                $previewRightContainer.hide();
                $previewLeftContainer.hide();
                alert('Пожалуйста, выберите файл изображения');
            }
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
            
        } catch (error) {
            console.error('Error loading result:', error);
            $statusBadge.text('Ошибка').removeClass().addClass('badge bg-danger status-badge ms-2');
        }
    }
});
