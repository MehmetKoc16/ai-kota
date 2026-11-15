using System.Drawing.Imaging;

namespace KotaTepsi;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        string? onizlemePng = null;
        string? veriYolu = null;

        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--onizleme" && i + 1 < args.Length)
            {
                onizlemePng = args[++i];
            }
            else if (args[i] == "--veri" && i + 1 < args.Length)
            {
                veriYolu = args[++i];
            }
        }

        if (!string.IsNullOrWhiteSpace(onizlemePng))
        {
            ApplicationConfiguration.Initialize();
            string hedefVeri = string.IsNullOrWhiteSpace(veriYolu)
                ? Path.Combine(TepsiUygulamasi.VeriDiziniBul(), "kota.json")
                : veriYolu;
            var veri = KotaVerisi.Oku(hedefVeri);
            using var bmp = KotaPaneli.OnizlemeCiz(veri, 360, DateTimeOffset.Now);

            string? klasor = Path.GetDirectoryName(Path.GetFullPath(onizlemePng));
            if (!string.IsNullOrEmpty(klasor))
                Directory.CreateDirectory(klasor);

            bmp.Save(onizlemePng, ImageFormat.Png);
            return;
        }

        using var mutex = new Mutex(initiallyOwned: true, name: "KotaTepsi_TekOrnek", out bool ilkOrnek);
        if (!ilkOrnek)
            return;

        ApplicationConfiguration.Initialize();
        Application.Run(new TepsiUygulamasi());
    }
}
